from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.repositories.base import BaseRepository
from app.models.models import Anomaly

class AnomalyRepository(BaseRepository[Anomaly]):
    def __init__(self):
        super().__init__(Anomaly)

    def get_active_anomalies(self, db: Session, store_id: str) -> List[Anomaly]:
        return db.query(Anomaly).filter(
            Anomaly.store_id == store_id,
            Anomaly.status == "Active"
        ).order_by(Anomaly.timestamp.desc()).all()

    def resolve_anomaly(self, db: Session, anomaly_id: str, action_taken: str) -> Optional[Anomaly]:
        anomaly = self.get(db, anomaly_id)
        if anomaly:
            anomaly.status = "Resolved"
            anomaly.action_taken = action_taken
            db.commit()
            db.refresh(anomaly)
        return anomaly

anomaly_repo = AnomalyRepository()
