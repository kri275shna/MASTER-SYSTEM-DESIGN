# PROMPT: Implement unified event ingestion service with new schema columns
# CHANGES MADE: Overwrote ingestion.py to handle schema-based insertion, duplicate detection, track lifecycle updates, and websocket broadcasts

import json
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.models.models import Event, VisitorSession, VisitorTrack, Store, Zone
from app.repositories.event_repository import event_repo
from app.repositories.visitor_repository import visitor_repo
from app.core.database import redis_client
from app.schemas.event import EventSchema

logger = logging.getLogger(__name__)

class IngestionService:
    def ingest_event(self, db: Session, store_id: str, camera_id: str, event_type: str, timestamp: datetime, payload: dict) -> Event:
        """
        Backward-compatible ingestion method. Wraps inputs into EventSchema and delegates.
        """
        # Convert timestamp to naive UTC
        if timestamp and timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)

        event_schema = EventSchema(
            store_id=store_id,
            camera_id=camera_id,
            visitor_id=payload.get("visitor_id") or "visitor-anon",
            event_type=event_type,
            timestamp=timestamp,
            zone_id=payload.get("zone_id"),
            dwell_ms=payload.get("dwell_time", 0) * 1000 if "dwell_time" in payload else 0,
            is_staff=payload.get("is_staff", False),
            confidence=payload.get("confidence", 1.0),
            metadata=payload
        )
        return self.ingest_event_schema(db, event_schema)

    def ingest_event_schema(self, db: Session, event_schema: EventSchema) -> Event:
        """
        Ingests a validated EventSchema event. Saves to database and broadcasts.
        """
        # 1. Deduplication: Check if event_id is already in PostgreSQL
        existing_event = db.query(Event).filter(Event.event_id == event_schema.event_id).first()
        if existing_event:
            logger.info(f"Duplicate event detected in PostgreSQL. Skipping ingestion: {event_schema.event_id}")
            return existing_event

        # Ensure datetime is naive UTC
        timestamp = event_schema.timestamp
        if timestamp and timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)

        visitor_id = event_schema.visitor_id
        store_id = event_schema.store_id
        camera_id = event_schema.camera_id
        event_type = event_schema.event_type
        zone_id = event_schema.zone_id

        # 2. Resolve or create Visitor Session
        session = self._resolve_session(db, store_id, visitor_id, event_type, timestamp, event_schema.is_staff)

        # 3. Add or update Visitor Track if camera details exist
        if camera_id and visitor_id:
            track = db.query(VisitorTrack).filter(
                VisitorTrack.session_id == session.id,
                VisitorTrack.camera_id == camera_id,
                VisitorTrack.track_id == visitor_id
            ).first()
            
            if not track:
                visitor_repo.add_track(
                    db,
                    session_id=session.id,
                    camera_id=camera_id,
                    track_id=visitor_id,
                    first_seen=timestamp,
                    feature_vector=event_schema.metadata.get("reid_features")
                )
            else:
                visitor_repo.update_track_last_seen(db, visitor_id, camera_id, timestamp)

        # 4. Process zone-specific events & dwell times
        dwell_ms = event_schema.dwell_ms or 0
        if event_type == "ZONE_EXIT":
            # If dwell_ms is not provided or 0, compute it from matching ZONE_ENTER in DB
            if dwell_ms == 0:
                enter_event = db.query(Event).filter(
                    Event.session_id == session.id,
                    Event.event_type == "ZONE_ENTER",
                    Event.zone_id == zone_id,
                    Event.timestamp < timestamp
                ).order_by(Event.timestamp.desc()).first()
                
                if enter_event:
                    dwell_sec = int((timestamp - enter_event.timestamp).total_seconds())
                    dwell_ms = dwell_sec * 1000
                    
            # Update visitor session cumulative dwell time
            session.total_dwell_time += int(dwell_ms / 1000)
            db.add(session)
            
            # Generate a subsequent ZONE_DWELL event log
            dwell_event = Event(
                event_id=f"dwell-{event_schema.event_id}",
                store_id=store_id,
                session_id=session.id,
                camera_id=camera_id,
                visitor_id=visitor_id,
                event_type="ZONE_DWELL",
                zone_id=zone_id,
                timestamp=timestamp,
                dwell_ms=dwell_ms,
                is_staff=session.is_staff,
                confidence=event_schema.confidence,
                event_metadata={"visitor_id": visitor_id, "dwell_ms": dwell_ms},
                payload={"visitor_id": visitor_id, "dwell_time": int(dwell_ms / 1000)}
            )
            db.add(dwell_event)

        # 5. Handle exit events
        if event_type == "EXIT":
            session.end_time = timestamp
            # Calculate total session duration
            session.total_dwell_time = int((timestamp - session.start_time).total_seconds())
            db.add(session)
            
            # Decrement active visitor counts in Redis
            if not session.is_staff:
                redis_client.decr(f"store:{store_id}:active_visitors")
        elif event_type == "ENTRY":
            # Increment active visitor counts in Redis
            if not session.is_staff:
                redis_client.incr(f"store:{store_id}:active_visitors")

        # 6. Create event in database
        event = Event(
            event_id=event_schema.event_id,
            store_id=store_id,
            session_id=session.id,
            camera_id=camera_id,
            visitor_id=visitor_id,
            event_type=event_type,
            zone_id=zone_id,
            timestamp=timestamp,
            dwell_ms=dwell_ms,
            is_staff=session.is_staff,
            confidence=event_schema.confidence,
            event_metadata=event_schema.metadata,
            payload={**(event_schema.metadata or {}), "visitor_id": visitor_id, "dwell_time": int(dwell_ms / 1000)}
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        # 7. Publish to Redis Pub/Sub channel for WebSockets
        self._publish_to_websocket(store_id, event, session)
        
        # 8. Update Redis metrics buffers
        self._update_redis_realtime_metrics(store_id, event_type, event_schema.metadata or {})

        return event

    def _resolve_session(self, db: Session, store_id: str, visitor_id: str, event_type: str, timestamp: datetime, is_staff_payload: bool) -> VisitorSession:
        """
        Resolves active visitor sessions, handling brief exits and re-entries.
        """
        # Look for active session in the store
        session = visitor_repo.get_active_session_by_visitor(db, store_id, visitor_id)
        
        # If no active session, check for a recently closed session (within 30 mins) to handle brief Re-entry
        if not session and event_type == "ENTRY":
            recent_session = db.query(VisitorSession).filter(
                VisitorSession.store_id == store_id,
                VisitorSession.unique_visitor_id == visitor_id,
                VisitorSession.end_time >= timestamp - timedelta(minutes=30)
            ).order_by(VisitorSession.end_time.desc()).first()
            
            if recent_session:
                # Capture exit time
                prev_exit = recent_session.end_time
                
                # Re-activate the session
                session = recent_session
                session.end_time = None
                db.add(session)
                
                # Save REENTRY event log
                reentry_event = Event(
                    event_id=f"reentry-{visitor_id}-{int(timestamp.timestamp())}",
                    store_id=store_id,
                    session_id=session.id,
                    visitor_id=visitor_id,
                    event_type="REENTRY",
                    timestamp=timestamp,
                    is_staff=session.is_staff,
                    event_metadata={"visitor_id": visitor_id, "previous_exit": prev_exit.isoformat() if prev_exit else None},
                    payload={"visitor_id": visitor_id, "previous_exit": prev_exit.isoformat() if prev_exit else None}
                )
                db.add(reentry_event)
                logger.info(f"Re-entry detected for visitor {visitor_id}. Re-activating session {session.id}.")

        if not session:
            # Create brand new session
            session = VisitorSession(
                unique_visitor_id=visitor_id,
                store_id=store_id,
                start_time=timestamp,
                is_staff=is_staff_payload,
                converted=False,
                total_dwell_time=0
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            logger.info(f"Created new session {session.id} for visitor {visitor_id}.")
            
        return session

    def _publish_to_websocket(self, store_id: str, event: Event, session: VisitorSession):
        """Pushes event payload to Redis channel for live WebSockets."""
        try:
            event_data = {
                "event_id": event.event_id,
                "store_id": event.store_id,
                "session_id": event.session_id,
                "camera_id": event.camera_id,
                "visitor_id": event.visitor_id,
                "event_type": event.event_type,
                "zone_id": event.zone_id,
                "timestamp": event.timestamp.isoformat(),
                "dwell_ms": event.dwell_ms,
                "is_staff": session.is_staff,
                "confidence": event.confidence,
                "metadata": event.event_metadata
            }
            redis_client.publish(f"store:{store_id}:events", json.dumps(event_data))
        except Exception as e:
            logger.error(f"Failed to publish event to Redis Pub/Sub: {e}")

    def _update_redis_realtime_metrics(self, store_id: str, event_type: str, payload: dict):
        """Updates real-time counters in Redis."""
        try:
            redis_client.hincrby(f"store:{store_id}:realtime", "total_events", 1)
            redis_client.hincrby(f"store:{store_id}:realtime", f"event:{event_type}", 1)
            
            # Queue depth tracking
            if event_type == "BILLING_QUEUE_JOIN":
                redis_client.incr(f"store:{store_id}:queue_depth")
            elif event_type in ["BILLING_QUEUE_LEAVE", "BILLING_QUEUE_ABANDON"]:
                redis_client.decr(f"store:{store_id}:queue_depth")
                if event_type == "BILLING_QUEUE_ABANDON":
                    redis_client.hincrby(f"store:{store_id}:realtime", "queue_abandons", 1)
        except Exception as e:
            logger.error(f"Failed to update real-time Redis metrics: {e}")

ingestion_service = IngestionService()
