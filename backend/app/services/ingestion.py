import json
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.models.models import Event, VisitorSession, VisitorTrack, Store, Zone
from app.repositories.event_repository import event_repo
from app.repositories.visitor_repository import visitor_repo
from app.core.database import redis_client

logger = logging.getLogger(__name__)

class IngestionService:
    def ingest_event(self, db: Session, store_id: str, camera_id: str, event_type: str, timestamp: datetime, payload: dict) -> Event:
        """
        Processes and stores visitor events.
        Maintains unique sessions, handles staff filtering, and publishes events to Redis.
        """
        # Convert timestamp to timezone-naive UTC to prevent offset comparisons error with database datetimes
        if timestamp and timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)

        visitor_id = payload.get("visitor_id")
        zone_id = payload.get("zone_id")
        
        # 1. Resolve or create Visitor Session
        session = self._resolve_session(db, store_id, visitor_id, event_type, timestamp, payload)
        
        # 2. Add or update Visitor Track if camera details exist
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
                    feature_vector=payload.get("reid_features")
                )
            else:
                visitor_repo.update_track_last_seen(db, visitor_id, camera_id, timestamp)

        # 3. Process zone-specific events & dwell times
        if event_type == "ZONE_EXIT":
            # Find matching ZONE_ENTER to compute dwell time
            enter_event = db.query(Event).filter(
                Event.session_id == session.id,
                Event.event_type == "ZONE_ENTER",
                Event.zone_id == zone_id,
                Event.timestamp < timestamp
            ).order_by(Event.timestamp.desc()).first()
            
            if enter_event:
                dwell_sec = int((timestamp - enter_event.timestamp).total_seconds())
                payload["dwell_time"] = dwell_sec
                
                # Update visitor session cumulative dwell time
                session.total_dwell_time += dwell_sec
                db.add(session)
                
                # Generate a subsequent DWELL event
                dwell_event = Event(
                    store_id=store_id,
                    session_id=session.id,
                    camera_id=camera_id,
                    event_type="ZONE_DWELL",
                    zone_id=zone_id,
                    timestamp=timestamp,
                    payload={"visitor_id": visitor_id, "dwell_time": dwell_sec}
                )
                db.add(dwell_event)

        # 4. Handle exit events
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

        # 5. Create event in database
        event = Event(
            store_id=store_id,
            session_id=session.id,
            camera_id=camera_id,
            event_type=event_type,
            zone_id=zone_id,
            timestamp=timestamp,
            payload=payload
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        # 6. Publish to Redis Pub/Sub channel for WebSockets
        self._publish_to_websocket(store_id, event, session)
        
        # 7. Update Redis metrics buffers
        self._update_redis_realtime_metrics(store_id, event_type, payload)

        return event

    def _resolve_session(self, db: Session, store_id: str, visitor_id: str, event_type: str, timestamp: datetime, payload: dict) -> VisitorSession:
        """
        Determines if an event belongs to an existing active session (re-entry aware)
        or represents a new unique visitor session.
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
                # Capture exit time before resetting it to None due to object reference sharing
                prev_exit = recent_session.end_time
                
                # Re-activate the session
                session = recent_session
                session.end_time = None
                db.add(session)
                
                # Save REENTRY event log
                reentry_event = Event(
                    store_id=store_id,
                    session_id=session.id,
                    event_type="REENTRY",
                    timestamp=timestamp,
                    payload={"visitor_id": visitor_id, "previous_exit": prev_exit.isoformat() if prev_exit else None}
                )
                db.add(reentry_event)
                logger.info(f"Re-entry detected for visitor {visitor_id}. Re-activating session {session.id}.")

        if not session:
            # Create brand new session
            is_staff = payload.get("is_staff", False)
            session = VisitorSession(
                unique_visitor_id=visitor_id,
                store_id=store_id,
                start_time=timestamp,
                is_staff=is_staff,
                converted=False,
                total_dwell_time=0
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            logger.info(f"Created new session {session.id} for visitor {visitor_id}.")
            
        return session

    def _publish_to_websocket(self, store_id: str, event: Event, session: VisitorSession):
        """
        Pushes events to Redis channel to be broadcasted via WebSockets.
        """
        try:
            event_data = {
                "id": event.id,
                "store_id": event.store_id,
                "session_id": event.session_id,
                "camera_id": event.camera_id,
                "event_type": event.event_type,
                "zone_id": event.zone_id,
                "timestamp": event.timestamp.isoformat(),
                "payload": event.payload,
                "is_staff": session.is_staff
            }
            redis_client.publish(f"store:{store_id}:events", json.dumps(event_data))
        except Exception as e:
            logger.error(f"Failed to publish event to Redis Pub/Sub: {e}")

    def _update_redis_realtime_metrics(self, store_id: str, event_type: str, payload: dict):
        """
        Updates short-term Redis buffers for lightning-fast dashboard counter checks.
        """
        try:
            # Increment total event counters
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
