from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import logging
import json
from sqlalchemy.orm import Session
from app.models.models import Anomaly, Event, VisitorSession, Camera, Zone
from app.repositories.anomaly_repository import anomaly_repo
from app.core.database import redis_client

logger = logging.getLogger(__name__)

class AnomalyEngine:
    def check_billing_queue_spike(self, db: Session, store_id: str) -> Optional[Anomaly]:
        """
        Detects if billing queue has spiked (e.g. depth > 7 people).
        """
        try:
            queue_depth = int(redis_client.get(f"store:{store_id}:queue_depth") or 0)
        except Exception:
            queue_depth = 0
            
        if queue_depth >= 7:
            # Check if active anomaly already exists
            existing = db.query(Anomaly).filter(
                Anomaly.store_id == store_id,
                Anomaly.anomaly_type == "BILLING_QUEUE_SPIKE",
                Anomaly.status == "Active"
            ).first()
            
            if not existing:
                anomaly = Anomaly(
                    store_id=store_id,
                    anomaly_type="BILLING_QUEUE_SPIKE",
                    severity="Warning" if queue_depth < 12 else "Critical",
                    message=f"Billing queue length has spiked to {queue_depth} visitors.",
                    timestamp=datetime.now(timezone.utc),
                    status="Active"
                )
                db.add(anomaly)
                db.commit()
                db.refresh(anomaly)
                self._publish_alert(store_id, anomaly)
                return anomaly
        return None

    def check_conversion_drop(self, db: Session, store_id: str) -> Optional[Anomaly]:
        """
        Detects if conversion rate drops below 12% over the last 4 hours (given active visitor sessions).
        """
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=4)
        
        sessions = db.query(VisitorSession).filter(
            VisitorSession.store_id == store_id,
            VisitorSession.is_staff == False,
            VisitorSession.start_time >= start_time
        ).all()
        
        unique_visitors = len(set(s.unique_visitor_id for s in sessions))
        converted = len(set(s.unique_visitor_id for s in sessions if s.converted))
        
        # Only check if there's representative traffic
        if unique_visitors >= 10:
            rate = (converted / unique_visitors) * 100
            if rate < 12.0:
                existing = db.query(Anomaly).filter(
                    Anomaly.store_id == store_id,
                    Anomaly.anomaly_type == "CONVERSION_DROP",
                    Anomaly.status == "Active"
                ).first()
                
                if not existing:
                    anomaly = Anomaly(
                        store_id=store_id,
                        anomaly_type="CONVERSION_DROP",
                        severity="Critical",
                        message=f"Store conversion rate has dropped to {round(rate, 1)}% over the last 4 hours.",
                        timestamp=now,
                        status="Active"
                    )
                    db.add(anomaly)
                    db.commit()
                    db.refresh(anomaly)
                    self._publish_alert(store_id, anomaly)
                    return anomaly
        return None

    def check_dead_zones(self, db: Session, store_id: str) -> List[Anomaly]:
        """
        Detects if any zone has received zero entries in the last 2 hours while there is store traffic.
        """
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=2)
        
        # Check overall store traffic
        total_events = db.query(Event).filter(
            Event.store_id == store_id,
            Event.timestamp >= start_time
        ).count()
        
        if total_events < 20:
            return []  # Low traffic overall, don't trigger dead zone alerts
            
        zones = db.query(Zone).filter(Zone.store_id == store_id).all()
        detected = []
        
        for zone in zones:
            zone_entries = db.query(Event).filter(
                Event.store_id == store_id,
                Event.zone_id == zone.id,
                Event.event_type == "ZONE_ENTER",
                Event.timestamp >= start_time
            ).count()
            
            if zone_entries == 0:
                existing = db.query(Anomaly).filter(
                    Anomaly.store_id == store_id,
                    Anomaly.anomaly_type == "DEAD_ZONE",
                    Anomaly.message.like(f"%{zone.name}%"),
                    Anomaly.status == "Active"
                ).first()
                
                if not existing:
                    anomaly = Anomaly(
                        store_id=store_id,
                        anomaly_type="DEAD_ZONE",
                        severity="Warning",
                        message=f"Zone '{zone.name}' has received zero visitor entries in the last 2 hours.",
                        timestamp=now,
                        status="Active"
                    )
                    db.add(anomaly)
                    db.commit()
                    db.refresh(anomaly)
                    self._publish_alert(store_id, anomaly)
                    detected.append(anomaly)
                    
        return detected

    def check_stale_feeds(self, db: Session, store_id: str) -> List[Anomaly]:
        """
        Detects if active cameras have stopped sending events for more than 15 minutes.
        """
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
            
            # If no events at all or older than 15 mins, flag it
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
                        status="Active"
                    )
                    db.add(anomaly)
                    db.commit()
                    db.refresh(anomaly)
                    self._publish_alert(store_id, anomaly)
                    detected.append(anomaly)
                    
        return detected

    def run_all_checks(self, db: Session, store_id: str) -> List[Anomaly]:
        self.check_billing_queue_spike(db, store_id)
        self.check_conversion_drop(db, store_id)
        self.check_dead_zones(db, store_id)
        self.check_stale_feeds(db, store_id)
        return anomaly_repo.get_active_anomalies(db, store_id)

    def _publish_alert(self, store_id: str, anomaly: Anomaly):
        """
        Publishes alerts to Redis for real-time WebSocket dashboard pushing.
        """
        try:
            alert_payload = {
                "id": anomaly.id,
                "store_id": anomaly.store_id,
                "anomaly_type": anomaly.anomaly_type,
                "severity": anomaly.severity,
                "message": anomaly.message,
                "timestamp": anomaly.timestamp.isoformat(),
                "status": anomaly.status
            }
            redis_client.publish(f"store:{store_id}:events", json.dumps({
                "event_type": "ANOMALY_ALERT",
                "timestamp": anomaly.timestamp.isoformat(),
                "payload": alert_payload
            }))
        except Exception as e:
            logger.error(f"Failed to publish anomaly to Redis Pub/Sub: {e}")

anomaly_engine = AnomalyEngine()
