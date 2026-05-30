from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
from app.repositories.base import BaseRepository
from app.models.models import MetricSnapshot

class MetricsRepository(BaseRepository[MetricSnapshot]):
    def __init__(self):
        super().__init__(MetricSnapshot)

    def get_latest_snapshot(self, db: Session, store_id: str) -> Optional[MetricSnapshot]:
        return db.query(MetricSnapshot).filter(
            MetricSnapshot.store_id == store_id
        ).order_by(MetricSnapshot.timestamp.desc()).first()

    def get_snapshots_in_range(self, db: Session, store_id: str, start: datetime, end: datetime) -> List[MetricSnapshot]:
        return db.query(MetricSnapshot).filter(
            MetricSnapshot.store_id == store_id,
            MetricSnapshot.timestamp >= start,
            MetricSnapshot.timestamp <= end
        ).order_by(MetricSnapshot.timestamp.asc()).all()

metrics_repo = MetricsRepository()
