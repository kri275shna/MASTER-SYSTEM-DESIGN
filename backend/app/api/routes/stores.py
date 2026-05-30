from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from app.core.database import get_db
from app.services.analytics import analytics_service
from app.services.funnel import funnel_service
from app.services.anomalies import anomaly_engine
from app.repositories.anomaly_repository import anomaly_repo
from app.api.dependencies.auth import get_current_user, RoleChecker
from app.models.models import Store, Camera, Zone, Transaction, User, VisitorSession
from app.schemas.schemas import (
    StoreResponse, StoreCreate, 
    CameraResponse, CameraCreate, 
    ZoneResponse, ZoneCreate,
    MetricsResponse, FunnelResponse, HeatmapItem, AnomalyResponse
)

router = APIRouter()

# --- ANALYTICS AND INTEL ENDPOINTS ---

@router.get("/{id}/metrics", response_model=MetricsResponse)
def get_store_metrics(
    id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves aggregated store traffic, conversion, and queue performance metrics.
    """
    store = db.query(Store).filter(Store.id == id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return analytics_service.get_store_metrics(db, id, start_time, end_time)

@router.get("/{id}/funnel", response_model=FunnelResponse)
def get_store_funnel(
    id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns store conversion funnel stages and average step transition times.
    """
    store = db.query(Store).filter(Store.id == id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return funnel_service.get_funnel_analytics(db, id, start_time, end_time)

@router.get("/{id}/heatmap", response_model=List[HeatmapItem])
def get_store_heatmap(
    id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns visitor counts and average dwell times broken down by zone.
    """
    store = db.query(Store).filter(Store.id == id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return analytics_service.get_zone_heatmap(db, id, start_time, end_time)

@router.get("/{id}/anomalies", response_model=List[AnomalyResponse])
def get_store_anomalies(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Triggers checking systems and retrieves all currently active store anomalies.
    """
    store = db.query(Store).filter(Store.id == id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    # Run dynamic anomaly scans
    anomaly_engine.run_all_checks(db, id)
    return anomaly_repo.get_active_anomalies(db, id)

@router.post("/{id}/anomalies/{anomaly_id}/resolve", response_model=AnomalyResponse)
def resolve_anomaly(
    id: str,
    anomaly_id: str,
    action_taken: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["Admin", "Analyst"]))
):
    """
    Marks an active anomaly alert as resolved.
    """
    anomaly = anomaly_repo.resolve_anomaly(db, anomaly_id, action_taken)
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly alert not found")
    return anomaly

# --- METADATA CONFIGURATION ENDPOINTS ---

@router.post("", response_model=StoreResponse, status_code=status.HTTP_201_CREATED)
def create_store(
    store_in: StoreCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["Admin"]))
):
    store = Store(name=store_in.name, location=store_in.location, timezone=store_in.timezone)
    db.add(store)
    db.commit()
    db.refresh(store)
    return store

@router.get("", response_model=List[StoreResponse])
def list_stores(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Store).all()

@router.post("/{id}/cameras", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
def create_camera(
    id: str,
    camera_in: CameraCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["Admin"]))
):
    # Verify store exists
    store = db.query(Store).filter(Store.id == id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
        
    camera = Camera(
        store_id=id,
        name=camera_in.name,
        ip_address=camera_in.ip_address,
        stream_url=camera_in.stream_url,
        zone_id=camera_in.zone_id
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera

@router.get("/{id}/cameras", response_model=List[CameraResponse])
def list_store_cameras(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Camera).filter(Camera.store_id == id).all()

@router.post("/{id}/zones", response_model=ZoneResponse, status_code=status.HTTP_201_CREATED)
def create_zone(
    id: str,
    zone_in: ZoneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["Admin"]))
):
    # Verify store exists
    store = db.query(Store).filter(Store.id == id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
        
    zone = Zone(
        store_id=id,
        name=zone_in.name,
        bounding_box=zone_in.bounding_box
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone

@router.get("/{id}/zones", response_model=List[ZoneResponse])
def list_store_zones(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Zone).filter(Zone.store_id == id).all()

# POS Transaction Simulator Route (for drop-off calculation testing)
@router.post("/{id}/transactions")
def record_transaction(
    id: str,
    session_id: str,
    amount: float,
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["Admin", "Analyst"]))
):
    session = db.query(VisitorSession).filter(VisitorSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Visitor session not found")
        
    # Create transaction
    tx = Transaction(
        store_id=id,
        session_id=session_id,
        transaction_id=transaction_id,
        amount=amount,
        timestamp=datetime.now(timezone.utc)
    )
    db.add(tx)
    
    # Mark session as converted
    session.converted = True
    db.add(session)
    
    db.commit()
    return {"status": "success", "transaction_id": transaction_id}
