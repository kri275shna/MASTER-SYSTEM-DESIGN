# PROMPT: Fix funnel service facade namespace collision
# CHANGES MADE: Overwrote funnel.py to import funnel_service as core_funnel_service, avoiding recursion

from sqlalchemy.orm import Session
from datetime import datetime
from app.services.funnel_service import funnel_service as core_funnel_service

class FunnelServiceFacade:
    def get_funnel_analytics(self, db: Session, store_id: str, start_time: datetime = None, end_time: datetime = None):
        return core_funnel_service.get_funnel_analytics(db, store_id, start_time, end_time)

funnel_service = FunnelServiceFacade()
