# PROMPT: Implement Heatmap Service with normalized scores
# CHANGES MADE: Created heatmap_service.py calculating visits, average dwells, and relative hotspot normalization

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models.models import Zone, Event

logger = logging.getLogger(__name__)

class HeatmapService:
    def get_zone_heatmap(self, db: Session, store_id: str, start_time: datetime = None, end_time: datetime = None) -> List[Dict[str, Any]]:
        """
        Returns average visitor density and dwell times per zone, with normalized heat intensity scoring.
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

        zones = db.query(Zone).filter(Zone.store_id == store_id).all()
        heatmap_data = []
        
        max_visits = 0
        max_dwell = 0.0

        for zone in zones:
            # 1. Total entries in zone
            visits = db.query(Event).filter(
                Event.store_id == store_id,
                Event.zone_id == zone.id,
                Event.event_type == "ZONE_ENTER",
                Event.timestamp >= start_time,
                Event.timestamp <= end_time
            ).count()

            # 2. Average dwell time in zone
            dwell_events = db.query(Event).filter(
                Event.store_id == store_id,
                Event.zone_id == zone.id,
                Event.event_type == "ZONE_DWELL",
                Event.timestamp >= start_time,
                Event.timestamp <= end_time
            ).all()

            avg_dwell = 0.0
            if dwell_events:
                total_dwell_ms = sum(e.dwell_ms or 0 for e in dwell_events)
                avg_dwell = float(total_dwell_ms / 1000 / len(dwell_events))

            # Maintain maximum values for normalization calculations
            max_visits = max(max_visits, visits)
            max_dwell = max(max_dwell, avg_dwell)

            heatmap_data.append({
                "zone_id": zone.id,
                "zone_name": zone.name,
                "visitor_count": visits,
                "avg_dwell_time_seconds": round(avg_dwell, 1),
                "bounding_box": zone.bounding_box
            })

        # Calculate normalized score (0 to 100 scale) for visual highlighting in the dashboard
        for item in heatmap_data:
            visits = item["visitor_count"]
            dwell = item["avg_dwell_time_seconds"]

            visits_ratio = (visits / max_visits) if max_visits > 0 else 0.0
            dwell_ratio = (dwell / max_dwell) if max_dwell > 0 else 0.0
            
            # Weighted normalization: 60% visitor count, 40% dwell duration
            norm_score = (visits_ratio * 0.6 + dwell_ratio * 0.4) * 100
            item["normalized_score"] = round(norm_score, 1)

        return heatmap_data

heatmap_service = HeatmapService()
