# PROMPT: Refactor analytics.py to delegate to metrics_service and heatmap_service
# CHANGES MADE: Overwrote analytics.py with clean delegation calls to metrics_service and heatmap_service

from sqlalchemy.orm import Session
from datetime import datetime
from app.services.metrics_service import metrics_service
from app.services.heatmap_service import heatmap_service

class AnalyticsService:
    def get_store_metrics(self, db: Session, store_id: str, start_time: datetime = None, end_time: datetime = None):
        return metrics_service.get_store_metrics(db, store_id, start_time, end_time)

    def get_zone_heatmap(self, db: Session, store_id: str, start_time: datetime = None, end_time: datetime = None):
        return heatmap_service.get_zone_heatmap(db, store_id, start_time, end_time)

analytics_service = AnalyticsService()
