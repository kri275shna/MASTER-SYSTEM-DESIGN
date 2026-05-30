from typing import List
from sqlalchemy.orm import Session
from datetime import datetime
from app.repositories.base import BaseRepository
from app.models.models import Event

class EventRepository(BaseRepository[Event]):
    def __init__(self):
        super().__init__(Event)

    def get_events_for_session(self, db: Session, session_id: str) -> List[Event]:
        return db.query(Event).filter(Event.session_id == session_id).order_by(Event.timestamp.asc()).all()

    def get_events_in_range(self, db: Session, store_id: str, start: datetime, end: datetime) -> List[Event]:
        return db.query(Event).filter(
            Event.store_id == store_id,
            Event.timestamp >= start,
            Event.timestamp <= end
        ).order_by(Event.timestamp.asc()).all()

    def get_events_by_type_in_range(self, db: Session, store_id: str, event_types: List[str], start: datetime, end: datetime) -> List[Event]:
        return db.query(Event).filter(
            Event.store_id == store_id,
            Event.event_type.in_(event_types),
            Event.timestamp >= start,
            Event.timestamp <= end
        ).order_by(Event.timestamp.asc()).all()

event_repo = EventRepository()
