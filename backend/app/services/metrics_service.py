# PROMPT: Implement Metrics Service handling edge cases
# CHANGES MADE: Created metrics_service.py with division safeguards, staff filters, and caching

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models.models import VisitorSession, Event
from app.core.database import redis_client

logger = logging.getLogger(__name__)

class MetricsService:
    def get_store_metrics(self, db: Session, store_id: str, start_time: datetime = None, end_time: datetime = None) -> Dict[str, Any]:
        """
        Computes store metrics including unique visitors, conversion rate, avg dwell, and queue performance.
        Includes safeguards for empty stores, zero purchases, staff filter, and caching.
        """
        now = datetime.now(timezone.utc)
        if not start_time:
            start_time = now - timedelta(days=1)
        if not end_time:
            end_time = now

        # timezone-naive comparisons
        if start_time.tzinfo is not None:
            start_time = start_time.astimezone(timezone.utc).replace(tzinfo=None)
        if end_time.tzinfo is not None:
            end_time = end_time.astimezone(timezone.utc).replace(tzinfo=None)

        # Caching check
        cache_key = f"store:{store_id}:metrics:{start_time.isoformat()}:{end_time.isoformat()}"
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

        # Query all visitor sessions within timeframe
        sessions = db.query(VisitorSession).filter(
            VisitorSession.store_id == store_id,
            VisitorSession.start_time >= start_time,
            VisitorSession.start_time <= end_time
        ).all()

        # Filters: exclude staff
        visitor_sessions = [s for s in sessions if not s.is_staff]
        staff_count = len([s for s in sessions if s.is_staff])

        # Unique Visitors count
        unique_visitors = len(set(s.unique_visitor_id for s in visitor_sessions))

        # Converted visitors
        converted_visitors = len(set(s.unique_visitor_id for s in visitor_sessions if s.converted))

        # 1. Conversion Rate safeguard
        conversion_rate = (converted_visitors / unique_visitors * 100) if unique_visitors > 0 else 0.0

        # 2. Avg Dwell Time safeguard
        dwells = [s.total_dwell_time for s in visitor_sessions if s.total_dwell_time > 0]
        avg_dwell_time = float(sum(dwells) / len(dwells)) if dwells else 0.0

        # Queue counters
        queue_joins = db.query(Event).filter(
            Event.store_id == store_id,
            Event.event_type == "BILLING_QUEUE_JOIN",
            Event.timestamp >= start_time,
            Event.timestamp <= end_time
        ).count()

        queue_abandons = db.query(Event).filter(
            Event.store_id == store_id,
            Event.event_type == "BILLING_QUEUE_ABANDON",
            Event.timestamp >= start_time,
            Event.timestamp <= end_time
        ).count()

        # 3. Abandonment Rate safeguard
        abandonment_rate = (queue_abandons / queue_joins * 100) if queue_joins > 0 else 0.0

        # Current Queue Depth from Redis
        try:
            curr_queue_depth = int(redis_client.get(f"store:{store_id}:queue_depth") or 0)
            curr_queue_depth = max(0, curr_queue_depth)
        except Exception:
            curr_queue_depth = 0

        # Repeat visitors (visitors with >1 session)
        visitor_counts = {}
        for s in visitor_sessions:
            visitor_counts[s.unique_visitor_id] = visitor_counts.get(s.unique_visitor_id, 0) + 1
        repeat_visitors = sum(1 for count in visitor_counts.values() if count > 1)

        # Traffic flow trend hourly
        hourly_bins = {}
        for s in visitor_sessions:
            hour_str = s.start_time.strftime("%Y-%m-%d %H:00")
            hourly_bins[hour_str] = hourly_bins.get(hour_str, 0) + 1
        
        sorted_hours = sorted(hourly_bins.keys())
        hourly_traffic = [{"time": h, "count": hourly_bins[h]} for h in sorted_hours]

        metrics = {
            "unique_visitors": unique_visitors,
            "staff_sessions": staff_count,
            "converted_visitors": converted_visitors,
            "conversion_rate": round(conversion_rate, 2),
            "avg_dwell_time_seconds": round(avg_dwell_time, 1),
            "queue_depth": curr_queue_depth,
            "queue_joins": queue_joins,
            "queue_abandons": queue_abandons,
            "queue_abandonment_rate": round(abandonment_rate, 2),
            "repeat_visitors": repeat_visitors,
            "hourly_traffic": hourly_traffic,
            "timestamp": now.isoformat()
        }

        # Cache results for 10 seconds
        try:
            redis_client.setex(cache_key, 10, json.dumps(metrics))
        except Exception:
            pass

        return metrics

metrics_service = MetricsService()
