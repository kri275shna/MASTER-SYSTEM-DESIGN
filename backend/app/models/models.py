from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timezone
from app.core.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="Viewer", nullable=False)  # Admin, Analyst, Viewer
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

class Store(Base):
    __tablename__ = "stores"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    location = Column(String(255), nullable=True)
    timezone = Column(String(100), default="UTC", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    cameras = relationship("Camera", back_populates="store", cascade="all, delete-orphan")
    zones = relationship("Zone", back_populates="store", cascade="all, delete-orphan")
    sessions = relationship("VisitorSession", back_populates="store", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="store", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="store", cascade="all, delete-orphan")
    metrics = relationship("MetricSnapshot", back_populates="store", cascade="all, delete-orphan")
    anomalies = relationship("Anomaly", back_populates="store", cascade="all, delete-orphan")

class Camera(Base):
    __tablename__ = "cameras"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    store_id = Column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    ip_address = Column(String(50), nullable=True)
    stream_url = Column(String(512), nullable=True)
    zone_id = Column(String(36), ForeignKey("zones.id"), nullable=True)  # Primary zone monitored
    status = Column(String(50), default="Active", nullable=False)  # Active, Inactive, Stale
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    store = relationship("Store", back_populates="cameras")
    zone = relationship("Zone", foreign_keys=[zone_id])
    tracks = relationship("VisitorTrack", back_populates="camera", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="camera", cascade="all, delete-orphan")
    jobs = relationship("DetectionJob", back_populates="camera", cascade="all, delete-orphan")

class Zone(Base):
    __tablename__ = "zones"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    store_id = Column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)  # Entrance, Exit, Makeup, Checkout, etc.
    bounding_box = Column(JSON, nullable=True)  # Polygon coordinates
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    store = relationship("Store", back_populates="zones")
    events = relationship("Event", back_populates="zone", cascade="all, delete-orphan")

class VisitorSession(Base):
    __tablename__ = "visitor_sessions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    unique_visitor_id = Column(String(255), nullable=False, index=True)  # Consolidated ReID trace id
    store_id = Column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=True, index=True)
    is_staff = Column(Boolean, default=False, nullable=False, index=True)
    converted = Column(Boolean, default=False, nullable=False, index=True)
    total_dwell_time = Column(Integer, default=0, nullable=False)  # seconds
    
    store = relationship("Store", back_populates="sessions")
    tracks = relationship("VisitorTrack", back_populates="session", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="session", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="session", cascade="all, delete-orphan")

class VisitorTrack(Base):
    __tablename__ = "visitor_tracks"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("visitor_sessions.id"), nullable=False, index=True)
    camera_id = Column(String(36), ForeignKey("cameras.id"), nullable=False, index=True)
    track_id = Column(String(100), nullable=False)  # Local tracking ID from ByteTrack
    first_seen = Column(DateTime, nullable=False)
    last_seen = Column(DateTime, nullable=False)
    feature_vector = Column(JSON, nullable=True)  # OSNet feature vector (e.g. List of floats)
    
    session = relationship("VisitorSession", back_populates="tracks")
    camera = relationship("Camera", back_populates="tracks")

class Event(Base):
    __tablename__ = "events"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    event_id = Column(String(36), unique=True, nullable=False, index=True, default=generate_uuid)
    store_id = Column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("visitor_sessions.id"), nullable=True, index=True)
    camera_id = Column(String(36), ForeignKey("cameras.id"), nullable=True, index=True)
    visitor_id = Column(String(255), nullable=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)  # ENTRY, EXIT, ZONE_ENTER, ZONE_EXIT, etc.
    zone_id = Column(String(36), ForeignKey("zones.id"), nullable=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    dwell_ms = Column(Integer, default=0, nullable=True)
    is_staff = Column(Boolean, default=False, nullable=True)
    confidence = Column(Float, default=1.0, nullable=True)
    event_metadata = Column("metadata", JSON, nullable=True)
    payload = Column(JSON, nullable=True)  # Event-specific detailed data
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    store = relationship("Store", back_populates="events")
    session = relationship("VisitorSession", back_populates="events")
    camera = relationship("Camera", back_populates="events")
    zone = relationship("Zone", back_populates="events")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    store_id = Column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("visitor_sessions.id"), nullable=True, index=True)
    transaction_id = Column(String(255), unique=True, nullable=False, index=True)  # POS system invoice ID
    amount = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    
    store = relationship("Store", back_populates="transactions")
    session = relationship("VisitorSession", back_populates="transactions")

class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    store_id = Column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    metrics_data = Column(JSON, nullable=False)  # Aggregated counters
    
    store = relationship("Store", back_populates="metrics")

class Anomaly(Base):
    __tablename__ = "anomalies"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    store_id = Column(String(36), ForeignKey("stores.id"), nullable=False, index=True)
    anomaly_type = Column(String(100), nullable=False, index=True)  # BILLING_QUEUE_SPIKE, etc.
    severity = Column(String(50), nullable=False)  # Info, Warning, Critical
    message = Column(String(512), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    status = Column(String(50), default="Active", nullable=False)  # Active, Acknowledged, Resolved
    action_taken = Column(String(512), nullable=True)
    
    store = relationship("Store", back_populates="anomalies")

class DetectionJob(Base):
    __tablename__ = "detection_jobs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    camera_id = Column(String(36), ForeignKey("cameras.id"), nullable=False, index=True)
    status = Column(String(50), default="Idle", nullable=False)  # Idle, Running, Completed, Failed
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_log = Column(String(1024), nullable=True)
    
    camera = relationship("Camera", back_populates="jobs")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(255), nullable=True, index=True)
    action = Column(String(512), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    ip_address = Column(String(50), nullable=True)
