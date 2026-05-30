from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- AUTHENTICATION SCHEMAS ---
class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: str = "Viewer"  # Admin, Analyst, Viewer

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: Optional[str]
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str

# --- EVENT SCHEMAS ---
class EventIngestRequest(BaseModel):
    store_id: str
    camera_id: Optional[str] = None
    event_type: str = Field(..., description="ENTRY, EXIT, ZONE_ENTER, ZONE_EXIT, BILLING_QUEUE_JOIN, BILLING_QUEUE_ABANDON, REENTRY, etc.")
    timestamp: datetime
    payload: Dict[str, Any] = Field(default_factory=dict, description="Must include 'visitor_id'. Can optionally include 'is_staff', 'reid_features', 'zone_name', 'zone_id', 'amount' (for transactions).")

class EventResponse(BaseModel):
    id: str
    store_id: str
    session_id: Optional[str]
    camera_id: Optional[str]
    event_type: str
    zone_id: Optional[str]
    timestamp: datetime
    payload: Optional[Dict[str, Any]]
    processed_at: datetime

    class Config:
        from_attributes = True

# --- STORE SCHEMAS ---
class StoreCreate(BaseModel):
    name: str
    location: Optional[str] = None
    timezone: str = "UTC"

class StoreResponse(BaseModel):
    id: str
    name: str
    location: Optional[str]
    timezone: str
    created_at: datetime

    class Config:
        from_attributes = True

class CameraCreate(BaseModel):
    name: str
    store_id: str
    ip_address: Optional[str] = None
    stream_url: Optional[str] = None
    zone_id: Optional[str] = None

class CameraResponse(BaseModel):
    id: str
    store_id: str
    name: str
    ip_address: Optional[str]
    stream_url: Optional[str]
    zone_id: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class ZoneCreate(BaseModel):
    store_id: str
    name: str
    bounding_box: Optional[List[List[int]]] = None  # Coordinates list

class ZoneResponse(BaseModel):
    id: str
    store_id: str
    name: str
    bounding_box: Optional[List[List[int]]]
    created_at: datetime

    class Config:
        from_attributes = True

# --- ANALYTICS SCHEMAS ---
class TrafficTrendItem(BaseModel):
    time: str
    count: int

class MetricsResponse(BaseModel):
    unique_visitors: int
    staff_sessions: int
    converted_visitors: int
    conversion_rate: float
    avg_dwell_time_seconds: float
    queue_depth: int
    queue_joins: int
    queue_abandons: int
    queue_abandonment_rate: float
    repeat_visitors: int
    hourly_traffic: List[TrafficTrendItem]
    timestamp: str

class HeatmapItem(BaseModel):
    zone_id: str
    zone_name: str
    visitor_count: int
    avg_dwell_time_seconds: float
    bounding_box: Optional[Any] = None

class FunnelStage(BaseModel):
    name: str
    count: int
    percentage: float
    drop_off_percentage: float

class FunnelTransitionTimes(BaseModel):
    entry_to_zone: float
    zone_to_queue: float
    queue_to_purchase: float

class FunnelResponse(BaseModel):
    stages: List[FunnelStage]
    avg_transition_times_seconds: FunnelTransitionTimes

class AnomalyResponse(BaseModel):
    id: str
    store_id: str
    anomaly_type: str
    severity: str
    message: str
    timestamp: datetime
    status: str
    action_taken: Optional[str]

    class Config:
        from_attributes = True
