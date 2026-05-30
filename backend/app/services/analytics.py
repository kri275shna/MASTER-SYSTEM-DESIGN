from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
import json
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.models import VisitorSession, Event, Transaction, Zone
from app.repositories.visitor_repository import visitor_repo
from app.repositories.event_repository import event_repo
from app.core.database import redis_client

logger = logging.getLogger(__name__)

class AnalyticsService:
    def get_store_metrics(self, db: Session, store_id: str, start_time: datetime = None, end_time: datetime = None) -> Dict[str, Any]:
        """
        Computes key performance metrics for a store. Caches results in Redis.
        """
        now = datetime.now(timezone.utc)
        if not start_time:
            start_time = now - timedelta(days=1)
        if not end_time:
            end_time = now

        # Attempt to read from cache first for performance
        cache_key = f"store:{store_id}:metrics:{start_time.isoformat()}:{end_time.isoformat()}"
        cached_data = redis_client.get(cache_key)
        if cached_data:
            try:
                return json.loads(cached_data)
            except Exception:
                pass

        # 1. Fetch sessions in the timeframe (excluding staff for visitor counts)
        sessions = db.query(VisitorSession).filter(
            VisitorSession.store_id == store_id,
            VisitorSession.start_time >= start_time,
            VisitorSession.start_time <= end_time
        ).all()

        total_unique = len(set(s.unique_visitor_id for s in sessions if not s.is_staff))
        staff_sessions = len([s for s in sessions if s.is_staff])
        
        # Converted visitors (excluding staff)
        converted_visitors = len(set(s.unique_visitor_id for s in sessions if not s.is_staff and s.converted))
        
        # Conversion rate
        conversion_rate = (converted_visitors / total_unique * 100) if total_unique > 0 else 0.0

        # Dwell times (visitors only)
        visitor_dwells = [s.total_dwell_time for s in sessions if not s.is_staff and s.total_dwell_time > 0]
        avg_dwell_time = float(sum(visitor_dwells) / len(visitor_dwells)) if visitor_dwells else 0.0

        # 2. Compute Queue Metrics
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

        queue_abandon_rate = (queue_abandons / queue_joins * 100) if queue_joins > 0 else 0.0

        # Real-time current queue depth (fetched from Redis)
        try:
            curr_queue_depth = int(redis_client.get(f"store:{store_id}:queue_depth") or 0)
        except Exception:
            curr_queue_depth = 0

        # 3. Repeat Visitors
        visitor_session_counts = {}
        for s in sessions:
            if not s.is_staff:
                visitor_session_counts[s.unique_visitor_id] = visitor_session_counts.get(s.unique_visitor_id, 0) + 1
        
        repeat_visitors = sum(1 for count in visitor_session_counts.values() if count > 1)

        # 4. Traffic Flow trends (hourly counts)
        hourly_traffic = self._compute_hourly_traffic(sessions)

        metrics = {
            "unique_visitors": total_unique,
            "staff_sessions": staff_sessions,
            "converted_visitors": converted_visitors,
            "conversion_rate": round(conversion_rate, 2),
            "avg_dwell_time_seconds": round(avg_dwell_time, 1),
            "queue_depth": curr_queue_depth,
            "queue_joins": queue_joins,
            "queue_abandons": queue_abandons,
            "queue_abandonment_rate": round(queue_abandon_rate, 2),
            "repeat_visitors": repeat_visitors,
            "hourly_traffic": hourly_traffic,
            "timestamp": now.isoformat()
        }

        # Cache computed results for 5 minutes
        try:
            redis_client.setex(cache_key, 300, json.dumps(metrics))
        except Exception as e:
            logger.error(f"Failed to write metrics to Redis cache: {e}")

        return metrics

    def _compute_hourly_traffic(self, sessions: List[VisitorSession]) -> List[Dict[str, Any]]:
        """
        Groups entry times by hour to build traffic timeline.
        """
        hourly_bins = {}
        for s in sessions:
            if not s.is_staff:
                hour_str = s.start_time.strftime("%Y-%m-%d %H:00")
                hourly_bins[hour_str] = hourly_bins.get(hour_str, 0) + 1
        
        # Sort and construct trend list
        sorted_hours = sorted(hourly_bins.keys())
        return [{"time": h, "count": hourly_bins[h]} for h in sorted_hours]

    def get_zone_heatmap(self, db: Session, store_id: str, start_time: datetime = None, end_time: datetime = None) -> List[Dict[str, Any]]:
        """
        Returns average visitor density and dwell times per zone inside the store.
        """
        now = datetime.now(timezone.utc)
        if not start_time:
            start_time = now - timedelta(days=1)
        if not end_time:
            end_time = now

        zones = db.query(Zone).filter(Zone.store_id == store_id).all()
        heatmap_data = []

        for zone in zones:
            # Total entries in zone
            visits = db.query(Event).filter(
                Event.store_id == store_id,
                Event.zone_id == zone.id,
                Event.event_type == "ZONE_ENTER",
                Event.timestamp >= start_time,
                Event.timestamp <= end_time
            ).count()

            # Average dwell time in zone
            dwell_events = db.query(Event).filter(
                Event.store_id == store_id,
                Event.zone_id == zone.id,
                Event.event_type == "ZONE_DWELL",
                Event.timestamp >= start_time,
                Event.timestamp <= end_time
            ).all()

            avg_dwell = 0.0
            if dwell_events:
                total_dwell = sum(int(e.payload.get("dwell_time", 0)) for e in dwell_events)
                avg_dwell = total_dwell / len(dwell_events)

            heatmap_data.append({
                "zone_id": zone.id,
                "zone_name": zone.name,
                "visitor_count": visits,
                "avg_dwell_time_seconds": round(avg_dwell, 1),
                "bounding_box": zone.bounding_box
            })

        return heatmap_data

analytics_service = AnalyticsService()
