# PROMPT: Implement Anomaly Detection Engine rules (Queue Spike, Conversion Drop, Dead Zone)
# CHANGES MADE: Created anomaly_service.py with historical average calculations and specific challenge rules

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.models import Anomaly, Event, VisitorSession, Camera, Zone
from app.repositories.anomaly_repository import anomaly_repo
from app.core.database import redis_client

logger = logging.getLogger(__name__)

class AnomalyService:
    def check_billing_queue_spike(self, db: Session, store_id: str, threshold_multiplier: float = 2.0) -> Optional[Anomaly]:
        """
        Detects if current queue length is higher than historical average * threshold_multiplier.
        Rule: Current Queue > Historical Average * Threshold
        """
        try:
            current_queue = int(redis_client.get(f"store:{store_id}:queue_depth") or 0)
            current_queue = max(0, current_queue)
        except Exception:
            current_queue = 0

        # Calculate historical average queue depth (from metric snapshots or events)
        # Fallback to default of 2.5 if no history exists
        now = datetime.now(timezone.utc)
        start_history = now - timedelta(days=7)
        
        # Query total joins over last 7 days to estimate average queue depth per hour
        total_joins = db.query(Event).filter(
            Event.store_id == store_id,
            Event.event_type == "BILLING_QUEUE_JOIN",
            Event.timestamp >= start_history
        ).count()
        
        hours = 7 * 24
        hist_avg = max(1.0, total_joins / hours) if total_joins > 0 else 2.0
        
        limit = hist_avg * threshold_multiplier
        if current_queue >= 7 and current_queue > limit:
            existing = db.query(Anomaly).filter(
                Anomaly.store_id == store_id,
                Anomaly.anomaly_type == "QUEUE_SPIKE",
                Anomaly.status == "Active"
            ).first()
            
            if not existing:
                anomaly = Anomaly(
                    store_id=store_id,
                    anomaly_type="QUEUE_SPIKE",
                    severity="Critical" if current_queue >= 12 else "Warning",
                    message=f"Billing queue spiked to {current_queue} (Hist Avg: {hist_avg:.1f}, Threshold Limit: {limit:.1f}).",
                    timestamp=now,
                    status="Active",
                    action_taken=None
                )
                db.add(anomaly)
                db.commit()
                db.refresh(anomaly)
                self._publish_alert(store_id, anomaly, "Deploy additional checkout staff immediately.")
                return anomaly
        return None

    def check_conversion_drop(self, db: Session, store_id: str) -> Optional[Anomaly]:
        """
        Detects if current conversion rate is lower than the 7-day rolling average.
        Rule: Current Conversion < 7-Day Average
        """
        now = datetime.now(timezone.utc)
        
        # 1. Calculate current conversion (last 4 hours)
        current_start = now - timedelta(hours=4)
        current_sessions = db.query(VisitorSession).filter(
            VisitorSession.store_id == store_id,
            VisitorSession.is_staff == False,
            VisitorSession.start_time >= current_start
        ).all()
        
        curr_visitors = len(set(s.unique_visitor_id for s in current_sessions))
        curr_converts = len(set(s.unique_visitor_id for s in current_sessions if s.converted))
        curr_conversion = (curr_converts / curr_visitors * 100) if curr_visitors >= 5 else None
        
        if curr_conversion is None:
            return None # Insufficient data

        # 2. Calculate 7-day historical average
        hist_start = now - timedelta(days=7)
        hist_sessions = db.query(VisitorSession).filter(
            VisitorSession.store_id == store_id,
            VisitorSession.is_staff == False,
            VisitorSession.start_time >= hist_start,
            VisitorSession.start_time < current_start
        ).all()
        
        hist_visitors = len(set(s.unique_visitor_id for s in hist_sessions))
        hist_converts = len(set(s.unique_visitor_id for s in hist_sessions if s.converted))
        hist_avg_conversion = (hist_converts / hist_visitors * 100) if hist_visitors >= 10 else 15.0 # fallback

        if curr_conversion < hist_avg_conversion:
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
                    message=f"Conversion rate dropped to {curr_conversion:.1f}% (7-Day Avg: {hist_avg_conversion:.1f}%).",
                    timestamp=now,
                    status="Active",
                    action_taken=None
                )
                db.add(anomaly)
                db.commit()
                db.refresh(anomaly)
                self._publish_alert(store_id, anomaly, "Inspect cashier check-out speeds and verify sales associate presence.")
                return anomaly
        return None

    def check_dead_zones(self, db: Session, store_id: str) -> List[Anomaly]:
        """
        Detects if any zone has zero visits for the last 30 minutes while there is store traffic.
        Rule: No visits for 30 minutes
        """
        now = datetime.now(timezone.utc)
        thirty_mins_ago = now - timedelta(minutes=30)
        
        # Verify overall store traffic exists (to avoid alerts during closing hours)
        store_traffic = db.query(VisitorSession).filter(
            VisitorSession.store_id == store_id,
            VisitorSession.start_time >= thirty_mins_ago
        ).count()
        
        if store_traffic < 3:
            return []

        zones = db.query(Zone).filter(Zone.store_id == store_id).all()
        detected = []

        for zone in zones:
            visits = db.query(Event).filter(
                Event.store_id == store_id,
                Event.zone_id == zone.id,
                Event.event_type == "ZONE_ENTER",
                Event.timestamp >= thirty_mins_ago
            ).count()

            if visits == 0:
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
                        message=f"Zone '{zone.name}' has received zero visitor entries in the last 30 minutes.",
                        timestamp=now,
                        status="Active",
                        action_taken=None
                    )
                    db.add(anomaly)
                    db.commit()
                    db.refresh(anomaly)
                    self._publish_alert(store_id, anomaly, "Audit visual displays, product layouts, or camera visibility in this area.")
                    detected.append(anomaly)
        return detected

    def run_all_checks(self, db: Session, store_id: str) -> List[Anomaly]:
        self.check_billing_queue_spike(db, store_id)
        self.check_conversion_drop(db, store_id)
        self.check_dead_zones(db, store_id)
        return anomaly_repo.get_active_anomalies(db, store_id)

    def _publish_alert(self, store_id: str, anomaly: Anomaly, suggested_action: str):
        """Broadcasts alerts to Redis Pub/Sub channels."""
        try:
            alert_payload = {
                "id": anomaly.id,
                "store_id": anomaly.store_id,
                "anomaly_type": anomaly.anomaly_type,
                "severity": anomaly.severity,
                "message": anomaly.message,
                "timestamp": anomaly.timestamp.isoformat(),
                "status": anomaly.status,
                "suggested_action": suggested_action
            }
            redis_client.publish(f"store:{store_id}:events", json.dumps({
                "event_type": "ANOMALY_ALERT",
                "timestamp": anomaly.timestamp.isoformat(),
                "payload": alert_payload
            }))
        except Exception as e:
            logger.error(f"Failed to publish anomaly to Redis Pub/Sub: {e}")

anomaly_service = AnomalyService()
