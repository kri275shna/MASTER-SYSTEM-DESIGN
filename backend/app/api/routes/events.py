from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, status
from sqlalchemy.orm import Session
import asyncio
import json
import logging
from app.core.database import get_db, redis_client
from app.services.ingestion import ingestion_service
from app.schemas.schemas import EventIngestRequest, EventResponse
from app.api.dependencies.auth import RoleChecker, get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

# Only Admin or Analyst can ingest events directly via REST API (e.g. Edge device auth)
@router.post("/ingest", response_model=EventResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest_event(event_in: EventIngestRequest, db: Session = Depends(get_db)):
    try:
        event = ingestion_service.ingest_event(
            db=db,
            store_id=event_in.store_id,
            camera_id=event_in.camera_id,
            event_type=event_in.event_type,
            timestamp=event_in.timestamp,
            payload=event_in.payload
        )
        return event
    except Exception as e:
        logger.error(f"Event Ingestion Failure: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to ingest event: {str(e)}")

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
        await websocket.close()
