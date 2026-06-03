# PROMPT: Refactor anomalies.py to delegate to anomaly_service
# CHANGES MADE: Overwrote anomalies.py with delegation calls to anomaly_service

from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.models import Anomaly
from app.services.anomaly_service import anomaly_service

class AnomalyEngineFacade:
    def check_billing_queue_spike(self, db: Session, store_id: str) -> Optional[Anomaly]:
        return anomaly_service.check_billing_queue_spike(db, store_id)

    def check_conversion_drop(self, db: Session, store_id: str) -> Optional[Anomaly]:
        return anomaly_service.check_conversion_drop(db, store_id)

    def check_dead_zones(self, db: Session, store_id: str) -> List[Anomaly]:
        return anomaly_service.check_dead_zones(db, store_id)

    def check_stale_feeds(self, db: Session, store_id: str) -> List[Anomaly]:
        # Stale feeds checking logic remains identical. We can call check_stale_feeds or implement
        # a standard query on events
        from datetime import datetime, timezone, timedelta
        from app.models.models import Camera, Event
        from app.core.database import redis_client
        import json
        
        now = datetime.now(timezone.utc)
        threshold_time = now - timedelta(minutes=15)
        
        cameras = db.query(Camera).filter(
            Camera.store_id == store_id,
            Camera.status == "Active"
        ).all()
        
        detected = []
        for camera in cameras:
            last_event = db.query(Event).filter(
                Event.camera_id == camera.id
            ).order_by(Event.timestamp.desc()).first()
            
            if not last_event or last_event.timestamp < threshold_time:
                existing = db.query(Anomaly).filter(
                    Anomaly.store_id == store_id,
                    Anomaly.anomaly_type == "STALE_FEED",
                    Anomaly.message.like(f"%{camera.name}%"),
                    Anomaly.status == "Active"
                ).first()
                
                if not existing:
                    anomaly = Anomaly(
                        store_id=store_id,
                        anomaly_type="STALE_FEED",
                        severity="Critical",
                        message=f"Camera '{camera.name}' feed is stale. No frame events received since {last_event.timestamp.isoformat() if last_event else 'never'}.",
                        timestamp=now,
                        status="Active",
                        action_taken=None
                    )
                    db.add(anomaly)
                    db.commit()
                    db.refresh(anomaly)
                    
                    # Publish to web sockets
                    try:
                        redis_client.publish(f"store:{store_id}:events", json.dumps({
                            "event_type": "ANOMALY_ALERT",
                            "timestamp": anomaly.timestamp.isoformat(),
                            "payload": {
                                "id": anomaly.id,
                                "store_id": anomaly.store_id,
                                "anomaly_type": anomaly.anomaly_type,
                                "severity": anomaly.severity,
                                "message": anomaly.message,
                                "timestamp": anomaly.timestamp.isoformat(),
                                "status": anomaly.status
                            }
                        }))
                    except Exception:
                        pass
                    detected.append(anomaly)
        return detected

    def run_all_checks(self, db: Session, store_id: str) -> List[Anomaly]:
        anomaly_service.check_billing_queue_spike(db, store_id)
        anomaly_service.check_conversion_drop(db, store_id)
        anomaly_service.check_dead_zones(db, store_id)
        self.check_stale_feeds(db, store_id)
        from app.repositories.anomaly_repository import anomaly_repo
        return anomaly_repo.get_active_anomalies(db, store_id)

anomaly_engine = AnomalyEngineFacade()
