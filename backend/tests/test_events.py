import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta
from app.models.models import VisitorSession, Event

def test_ingest_entry_event(client: TestClient, db_session):
    # Setup - we need the seeded store which was initialized at startup
    store_id = "store-mumbai-01"
    
    # Ingest event
    payload = {
        "store_id": store_id,
        "camera_id": "cam-01",
        "event_type": "ENTRY",
        "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "payload": {
            "visitor_id": "test-visitor-999",
            "is_staff": False
        }
    }
    
    response = client.post("/api/v1/events/ingest", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["event_type"] == "ENTRY"
    assert data["store_id"] == store_id
    
    # Verify Session created in DB
    session = db_session.query(VisitorSession).filter(VisitorSession.unique_visitor_id == "test-visitor-999").first()
    assert session is not None
    assert session.is_staff is False
    assert session.end_time is None

def test_reentry_logic(client: TestClient, db_session):
    store_id = "store-mumbai-01"
    t_start = datetime.now(timezone.utc).replace(tzinfo=None)
    t_exit = t_start + timedelta(minutes=10)
    t_reentry = t_exit + timedelta(minutes=5) # 5 minutes is < 30 minutes
    
    # 1. Entry
    client.post("/api/v1/events/ingest", json={
        "store_id": store_id, "event_type": "ENTRY", "timestamp": t_start.isoformat(),
        "payload": {"visitor_id": "reenter-visitor-1"}
    })
    
    # Verify session active
    session = db_session.query(VisitorSession).filter(VisitorSession.unique_visitor_id == "reenter-visitor-1").first()
    session_id = session.id
    
    # 2. Exit
    client.post("/api/v1/events/ingest", json={
        "store_id": store_id, "event_type": "EXIT", "timestamp": t_exit.isoformat(),
        "payload": {"visitor_id": "reenter-visitor-1"}
    })
    db_session.refresh(session)
    assert session.end_time is not None
    
    # 3. Re-entry (same visitor ID, within 5 minutes)
    client.post("/api/v1/events/ingest", json={
        "store_id": store_id, "event_type": "ENTRY", "timestamp": t_reentry.isoformat(),
        "payload": {"visitor_id": "reenter-visitor-1"}
    })
    
    # Verify the same session was re-opened (end_time reset to None)
    db_session.refresh(session)
    assert session.id == session_id
    assert session.end_time is None
    
    # Check if a REENTRY log event was created
    reentry_log = db_session.query(Event).filter(
        Event.session_id == session.id,
        Event.event_type == "REENTRY"
    ).first()
    assert reentry_log is not None

def test_staff_detection_flag(client: TestClient, db_session):
    store_id = "store-mumbai-01"
    
    # Ingest event representing staff member
    client.post("/api/v1/events/ingest", json={
        "store_id": store_id,
        "event_type": "ENTRY",
        "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "payload": {
            "visitor_id": "staff-member-x",
            "is_staff": True
        }
    })
    
    # Verify session is flagged as staff
    session = db_session.query(VisitorSession).filter(VisitorSession.unique_visitor_id == "staff-member-x").first()
    assert session is not None
    assert session.is_staff is True
