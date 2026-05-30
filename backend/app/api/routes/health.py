from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import get_db
from app.services.health import health_service

router = APIRouter()

@router.get("", status_code=200)
def get_health_status(
    store_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Returns diagnostics of database, cache, and ingestion pipeline lag.
    """
    return health_service.get_system_health(db, store_id)
