# PROMPT: Implement Funnel Analytics Service with drop-offs
# CHANGES MADE: Created funnel_service.py calculating counts and percentages across stages with duration averages

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models.models import VisitorSession, Event, Transaction

logger = logging.getLogger(__name__)

class FunnelService:
    def get_funnel_analytics(self, db: Session, store_id: str, start_time: datetime = None, end_time: datetime = None) -> Dict[str, Any]:
        """
        Computes visitor conversion funnel: ENTRY -> ZONE_VISIT -> BILLING_QUEUE -> PURCHASE
        Includes counts, percentages, and drop-offs.
        """
        now = datetime.now(timezone.utc)
        if not start_time:
            start_time = now - timedelta(days=1)
        if not end_time:
            end_time = now

        # Convert to naive UTC
        if start_time.tzinfo is not None:
            start_time = start_time.astimezone(timezone.utc).replace(tzinfo=None)
        if end_time.tzinfo is not None:
            end_time = end_time.astimezone(timezone.utc).replace(tzinfo=None)

        # Get visitor sessions (excluding staff)
        sessions = db.query(VisitorSession).filter(
            VisitorSession.store_id == store_id,
            VisitorSession.is_staff == False,
            VisitorSession.start_time >= start_time,
            VisitorSession.start_time <= end_time
        ).all()

        session_ids = [s.id for s in sessions]
        entry_count = len(sessions)

        if entry_count == 0:
            return {
                "stages": [
                    {"name": "ENTRY", "count": 0, "percentage": 100.0, "drop_off_percentage": 0.0},
                    {"name": "ZONE_VISIT", "count": 0, "percentage": 0.0, "drop_off_percentage": 0.0},
                    {"name": "BILLING_QUEUE", "count": 0, "percentage": 0.0, "drop_off_percentage": 0.0},
                    {"name": "PURCHASE", "count": 0, "percentage": 0.0, "drop_off_percentage": 0.0}
                ],
                "avg_transition_times_seconds": {
                    "entry_to_zone": 0.0,
                    "zone_to_queue": 0.0,
                    "queue_to_purchase": 0.0
                }
            }

        # ZONE_VISIT stage: entered at least one zone
        zone_visits = db.query(Event.session_id).filter(
            Event.session_id.in_(session_ids),
            Event.event_type == "ZONE_ENTER"
        ).distinct().all()
        zone_visit_ids = {v[0] for v in zone_visits}
        zone_count = len(zone_visit_ids)

        # BILLING_QUEUE stage: joined queue
        queue_visits = db.query(Event.session_id).filter(
            Event.session_id.in_(session_ids),
            Event.event_type == "BILLING_QUEUE_JOIN"
        ).distinct().all()
        queue_visit_ids = {q[0] for q in queue_visits}
        queue_count = len(queue_visit_ids)

        # PURCHASE stage: converted
        purchase_sessions = [s for s in sessions if s.converted]
        purchase_count = len(purchase_sessions)

        # Calculate percentages relative to ENTRY stage
        zone_perc = (zone_count / entry_count) * 100
        queue_perc = (queue_count / entry_count) * 100
        purchase_perc = (purchase_count / entry_count) * 100

        # Calculate drop-off percentages from previous stage
        zone_drop = 100 - zone_perc
        queue_drop = 100 - (queue_count / zone_count * 100) if zone_count > 0 else 100.0
        purchase_drop = 100 - (purchase_count / queue_count * 100) if queue_count > 0 else 100.0

        # Calculate transition time averages
        entry_to_zone_durations = []
        zone_to_queue_durations = []
        queue_to_purchase_durations = []

        for s in sessions:
            events = db.query(Event).filter(Event.session_id == s.id).order_by(Event.timestamp.asc()).all()
            transaction = db.query(Transaction).filter(Transaction.session_id == s.id).first()

            first_enter = next((e for e in events if e.event_type == "ZONE_ENTER"), None)
            first_queue = next((e for e in events if e.event_type == "BILLING_QUEUE_JOIN"), None)

            if first_enter:
                entry_to_zone_durations.append((first_enter.timestamp - s.start_time).total_seconds())

            if first_enter and first_queue and first_queue.timestamp > first_enter.timestamp:
                zone_to_queue_durations.append((first_queue.timestamp - first_enter.timestamp).total_seconds())

            if first_queue and transaction and transaction.timestamp > first_queue.timestamp:
                queue_to_purchase_durations.append((transaction.timestamp - first_queue.timestamp).total_seconds())

        avg_entry_to_zone = sum(entry_to_zone_durations) / len(entry_to_zone_durations) if entry_to_zone_durations else 0.0
        avg_zone_to_queue = sum(zone_to_queue_durations) / len(zone_to_queue_durations) if zone_to_queue_durations else 0.0
        avg_queue_to_purchase = sum(queue_to_purchase_durations) / len(queue_to_purchase_durations) if queue_to_purchase_durations else 0.0

        return {
            "stages": [
                {"name": "ENTRY", "count": entry_count, "percentage": 100.0, "drop_off_percentage": 0.0},
                {"name": "ZONE_VISIT", "count": zone_count, "percentage": round(zone_perc, 2), "drop_off_percentage": round(zone_drop, 2)},
                {"name": "BILLING_QUEUE", "count": queue_count, "percentage": round(queue_perc, 2), "drop_off_percentage": round(queue_drop, 2)},
                {"name": "PURCHASE", "count": purchase_count, "percentage": round(purchase_perc, 2), "drop_off_percentage": round(purchase_drop, 2)}
            ],
            "avg_transition_times_seconds": {
                "entry_to_zone": round(avg_entry_to_zone, 1),
                "zone_to_queue": round(avg_zone_to_queue, 1),
                "queue_to_purchase": round(avg_queue_to_purchase, 1)
            }
        }

funnel_service = FunnelService()
