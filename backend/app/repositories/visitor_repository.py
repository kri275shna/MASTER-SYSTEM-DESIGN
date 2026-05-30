from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timezone
from app.repositories.base import BaseRepository
from app.models.models import VisitorSession, VisitorTrack

class VisitorRepository(BaseRepository[VisitorSession]):
    def __init__(self):
        super().__init__(VisitorSession)

    def get_active_session_by_visitor(self, db: Session, store_id: str, unique_visitor_id: str) -> Optional[VisitorSession]:
        """
        Retrieves the active session (where end_time is null or within last 30 minutes)
        to handle potential brief exits/re-entries as the same session.
        """
        return db.query(VisitorSession).filter(
            VisitorSession.store_id == store_id,
            VisitorSession.unique_visitor_id == unique_visitor_id,
            VisitorSession.end_time == None
        ).order_by(VisitorSession.start_time.desc()).first()

    def get_active_sessions_count(self, db: Session, store_id: str) -> int:
        return db.query(VisitorSession).filter(
            VisitorSession.store_id == store_id,
            VisitorSession.end_time == None
        ).count()

    def get_sessions_in_range(self, db: Session, store_id: str, start: datetime, end: datetime) -> List[VisitorSession]:
        return db.query(VisitorSession).filter(
            VisitorSession.store_id == store_id,
            VisitorSession.start_time >= start,
            VisitorSession.start_time <= end
        ).all()

    def add_track(self, db: Session, session_id: str, camera_id: str, track_id: str, first_seen: datetime, feature_vector: list = None) -> VisitorTrack:
        track = VisitorTrack(
            session_id=session_id,
            camera_id=camera_id,
            track_id=track_id,
            first_seen=first_seen,
            last_seen=first_seen,
            feature_vector=feature_vector
        )
        db.add(track)
        db.commit()
        db.refresh(track)
        return track

    def update_track_last_seen(self, db: Session, track_id: str, camera_id: str, last_seen: datetime) -> Optional[VisitorTrack]:
        track = db.query(VisitorTrack).filter(
            VisitorTrack.track_id == track_id,
            VisitorTrack.camera_id == camera_id
        ).order_by(VisitorTrack.first_seen.desc()).first()
        if track:
            track.last_seen = last_seen
            db.commit()
            db.refresh(track)
        return track

visitor_repo = VisitorRepository()
