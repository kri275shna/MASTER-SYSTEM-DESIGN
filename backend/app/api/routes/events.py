# PROMPT: Implement robust events ingestion supporting old and new schema payloads
# CHANGES MADE: Overwrote events.py route with dynamic format translator, validation, and stream emission

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
import asyncio
import json
import logging
import uuid
from typing import Union, List, Dict, Any
from datetime import datetime, timezone

from app.core.database import get_db, redis_client
from app.services.ingestion import ingestion_service
from app.services.event_producer import event_producer
from app.schemas.event import EventSchema
from app.api.dependencies.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

def translate_event(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translates old format event payload to the new EventSchema format.
    Old format uses 'payload' containing 'visitor_id', while the challenge schema expects top-level fields.
    """
    translated = raw.copy()
    
    # 1. Deduce event_id
    if "event_id" not in translated or not translated["event_id"]:
        translated["event_id"] = str(uuid.uuid4())

    # 2. Extract visitor_id and metadata from payload if old format is passed
    if "payload" in translated and "visitor_id" not in translated:
        payload = translated["payload"] or {}
        translated["visitor_id"] = payload.get("visitor_id") or "visitor-anon"
        translated["is_staff"] = payload.get("is_staff", False)
        translated["confidence"] = payload.get("confidence", 1.0)
        translated["dwell_ms"] = payload.get("dwell_time", 0) * 1000
        # Set metadata to payload dict
        translated["metadata"] = payload
    
    # Ensure metadata field is set
    if "metadata" not in translated or not translated["metadata"]:
        translated["metadata"] = {}

    return translated

@router.post("/ingest", status_code=status.HTTP_207_MULTI_STATUS)
def ingest_events(
    events_in: Union[Dict[str, Any], List[Dict[str, Any]]],
    response: Response,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Ingests a single event or a batch of events.
    Translates old format inputs, validates schemas, runs deduplication, and pushes to Redis Stream.
    """
    is_batch = isinstance(events_in, list)
    raw_events = events_in if is_batch else [events_in]
    
    # Track count for structlog logs
    request.state.event_count = len(raw_events)
    
    results = []
    validated_events = []
    
    for raw_evt in raw_events:
        try:
            # Translate inputs dynamically
            translated = translate_event(raw_evt)
            
            # Validate schema
            evt_schema = EventSchema(**translated)
            validated_events.append(evt_schema)
        except Exception as ve:
            logger.warning(f"Event validation failed: {ve}")
            results.append({
                "event_id": raw_evt.get("event_id") or "unknown",
                "status": "failed",
                "detail": f"Validation error: {str(ve)}"
            })

    # Process all validated events
    for evt in validated_events:
        # Check idempotency in Redis
        redis_key = f"event:processed:{evt.event_id}"
        if redis_client.get(redis_key):
            results.append({
                "event_id": evt.event_id,
                "status": "duplicate",
                "detail": "Duplicate event discarded (already processed)."
            })
            continue
            
        # Serialize to dict for stream
        evt_dict = evt.model_dump()
        evt_dict["timestamp"] = evt_dict["timestamp"].isoformat()
        
        # Buffer event in Redis Stream
        pushed = event_producer.produce_event(evt_dict)
        
        if pushed:
            results.append({
                "event_id": evt.event_id,
                "status": "accepted",
                "detail": "Event accepted and buffered in Redis stream queue."
            })
        else:
            # Synchronous fallback if Redis Stream is down or mocked
            try:
                ingestion_service.ingest_event_schema(db, evt)
                # Cache processed event ID in Redis for 24h
                redis_client.setex(redis_key, 86400, "1")
                results.append({
                    "event_id": evt.event_id,
                    "status": "success",
                    "detail": "Event processed and saved synchronously."
                })
            except Exception as e:
                logger.error(f"Fallback ingestion failed for event {evt.event_id}: {e}")
                results.append({
                    "event_id": evt.event_id,
                    "status": "failed",
                    "detail": f"Ingestion error: {str(e)}"
                })

    # Return structure matching single request expectations
    if not is_batch:
        res = results[0]
        if res["status"] in ["accepted", "success"]:
            response.status_code = status.HTTP_202_ACCEPTED
            evt = validated_events[0]
            return {
                "id": evt.event_id,
                "store_id": evt.store_id,
                "session_id": f"session-{evt.visitor_id}",
                "camera_id": evt.camera_id,
                "event_type": evt.event_type,
                "zone_id": evt.zone_id,
                "timestamp": evt.timestamp,
                "payload": evt.metadata,
                "processed_at": datetime.now(timezone.utc)
            }
        elif res["status"] == "duplicate":
            response.status_code = status.HTTP_200_OK
            return {"status": "duplicate", "detail": res["detail"]}
        else:
            response.status_code = status.HTTP_400_BAD_REQUEST
            raise HTTPException(status_code=400, detail=res["detail"])

    # Batch response format with 207 Multi-Status summary
    response.status_code = status.HTTP_207_MULTI_STATUS
    return {
        "summary": {
            "total": len(raw_events),
            "accepted": len([r for r in results if r["status"] == "accepted"]),
            "success": len([r for r in results if r["status"] == "success"]),
            "duplicate": len([r for r in results if r["status"] == "duplicate"]),
            "failed": len([r for r in results if r["status"] == "failed"])
        },
        "results": results
    }

# WebSocket route for real-time live dashboard updates
@router.websocket("/stores/{store_id}/events/stream")
async def websocket_event_stream(websocket: WebSocket, store_id: str):
    await websocket.accept()
    logger.info(f"WebSocket client connected to store stream: {store_id}")
    
    # Subscribe to Redis Channel for this store
    pubsub = redis_client.pubsub()
    pubsub.subscribe(f"store:{store_id}:events")
    
    try:
        while True:
            # We check for Redis messages in an async-friendly way
            # We run a small sleep so we don't CPU-block
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
            if message:
                data = message["data"]
                await websocket.send_text(data)
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected from store stream: {store_id}")
    except Exception as e:
        logger.error(f"WebSocket Error on store stream: {e}")
    finally:
        pubsub.unsubscribe(f"store:{store_id}:events")
        try:
            await websocket.close()
        except Exception:
            pass
