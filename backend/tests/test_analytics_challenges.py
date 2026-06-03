# PROMPT: Implement comprehensive testing for analytics edge cases including empty stores, duplicates, and anomalies.
# CHANGES MADE: Created test_analytics_challenges.py covering duplicate deduplication, re-entry session reuse, staff filtering, empty store divisions, zero purchases, queue spikes, dead zones, funnel percentages, and heatmap normalized scores.

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta
from app.models.models import VisitorSession, Event, Zone, Anomaly
from app.services.metrics_service import metrics_service
from app.services.funnel_service import funnel_service
from app.services.heatmap_service import heatmap_service
from app.services.anomaly_service import anomaly_service
from app.core.database import redis_client

@pytest.fixture
def auth_headers(client: TestClient):
    client.post(
        "/api/v1/auth/register",
        json={"email": "tester@purplle.com", "password": "testerpassword", "full_name": "Test User", "role": "Analyst"}
    )
    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": "tester@purplle.com", "password": "testerpassword"}
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_duplicate_events_deduplication(client: TestClient, db_session, auth_headers):
    store_id = "store-mumbai-01"
    event_id = "unique-evt-abc-123"
    timestamp = datetime.now(timezone.utc).isoformat()
    
    payload = {
        "event_id": event_id,
        "store_id": store_id,
        "camera_id": "cam-01",
        "visitor_id": "visitor-dup-test",
        "event_type": "ENTRY",
        "timestamp": timestamp,
        "confidence": 0.95,
        "is_staff": False
    }

    # First Ingest
    resp1 = client.post("/api/v1/events/ingest", json=payload, headers=auth_headers)
    assert resp1.status_code == 202
    
    # Second Ingest (Duplicate)
    resp2 = client.post("/api/v1/events/ingest", json=payload, headers=auth_headers)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "duplicate"

    # Query DB count
    count = db_session.query(Event).filter(Event.event_id == event_id).count()
    assert count == 1

def test_re_entry_session_logic(client: TestClient, db_session, auth_headers):
    store_id = "store-mumbai-01"
    visitor_id = "visitor-reentry-9"
    t_start = datetime.now(timezone.utc) - timedelta(minutes=45)
    t_exit = t_start + timedelta(minutes=10)
    t_reentry = t_exit + timedelta(minutes=15)  # 15 mins is < 30 mins

    # 1. Entry
    client.post("/api/v1/events/ingest", json={
        "store_id": store_id, "visitor_id": visitor_id, "event_type": "ENTRY", "timestamp": t_start.isoformat()
    }, headers=auth_headers)
    
    session = db_session.query(VisitorSession).filter(VisitorSession.unique_visitor_id == visitor_id).first()
    session_id = session.id
    
    # 2. Exit
    client.post("/api/v1/events/ingest", json={
        "store_id": store_id, "visitor_id": visitor_id, "event_type": "EXIT", "timestamp": t_exit.isoformat()
    }, headers=auth_headers)
    
    db_session.refresh(session)
    assert session.end_time is not None
    
    # 3. Re-entry (within 30 mins)
    client.post("/api/v1/events/ingest", json={
        "store_id": store_id, "visitor_id": visitor_id, "event_type": "ENTRY", "timestamp": t_reentry.isoformat()
    }, headers=auth_headers)
    
    db_session.refresh(session)
    # Verify same session is re-activated
    assert session.id == session_id
    assert session.end_time is None
    
    # Verify a REENTRY event log is generated
    reentry_log = db_session.query(Event).filter(Event.session_id == session_id, Event.event_type == "REENTRY").first()
    assert reentry_log is not None

def test_staff_exclusion_in_metrics(client: TestClient, db_session, auth_headers):
    store_id = "store-mumbai-01"
    now = datetime.now(timezone.utc)
    
    # Seed 1 staff session and 1 customer session
    s_staff = VisitorSession(unique_visitor_id="staff-99", store_id=store_id, start_time=now - timedelta(hours=1), is_staff=True, converted=False)
    s_cust = VisitorSession(unique_visitor_id="cust-11", store_id=store_id, start_time=now - timedelta(hours=1), is_staff=False, converted=True)
    db_session.add(s_staff)
    db_session.add(s_cust)
    db_session.commit()
    
    metrics = metrics_service.get_store_metrics(db_session, store_id, now - timedelta(hours=2), now + timedelta(hours=1))
    
    # Verify staff excluded from unique_visitors but registered in staff_sessions
    assert metrics["unique_visitors"] == 1
    assert metrics["staff_sessions"] == 1
    # 1 visitor converted out of 1 unique visitor -> 100% conversion
    assert metrics["conversion_rate"] == 100.0

def test_empty_store_safeguard(db_session):
    store_id = "store-mumbai-01"
    now = datetime.now(timezone.utc)
    
    metrics = metrics_service.get_store_metrics(db_session, store_id, now - timedelta(hours=1), now)
    assert metrics["unique_visitors"] == 0
    assert metrics["conversion_rate"] == 0.0
    assert metrics["avg_dwell_time_seconds"] == 0.0
    assert metrics["queue_abandonment_rate"] == 0.0

def test_zero_purchases_safeguard(db_session):
    store_id = "store-mumbai-01"
    now = datetime.now(timezone.utc)
    
    # Seed visitor with no conversion
    s = VisitorSession(unique_visitor_id="visitor-no-buy", store_id=store_id, start_time=now - timedelta(minutes=20), is_staff=False, converted=False)
    db_session.add(s)
    db_session.commit()
    
    metrics = metrics_service.get_store_metrics(db_session, store_id, now - timedelta(hours=1), now)
    assert metrics["unique_visitors"] == 1
    assert metrics["conversion_rate"] == 0.0

def test_queue_spike_anomaly(db_session):
    store_id = "store-mumbai-01"
    
    # Override Redis mock queue depth to high spike value
    redis_client.set(f"store:{store_id}:queue_depth", 10)
    
    # Clean active anomalies first
    db_session.query(Anomaly).filter(Anomaly.store_id == store_id).delete()
    db_session.commit()
    
    anomaly = anomaly_service.check_billing_queue_spike(db_session, store_id, threshold_multiplier=2.0)
    assert anomaly is not None
    assert anomaly.anomaly_type == "QUEUE_SPIKE"
    assert anomaly.severity in ["Warning", "Critical"]

def test_dead_zone_anomaly(db_session):
    store_id = "store-mumbai-01"
    
    # Delete active anomalies and seed visitor activity
    db_session.query(Anomaly).filter(Anomaly.store_id == store_id).delete()
    
    # Seed overall store traffic to enable dead zone scanning
    now = datetime.now(timezone.utc)
    for i in range(5):
        s = VisitorSession(unique_visitor_id=f"traffic-visitor-{i}", store_id=store_id, start_time=now - timedelta(minutes=10), is_staff=False)
        db_session.add(s)
    
    # Mumbai has 3 seeded zones: Entrance Zone, Cosmetics Section, Billing Queue Zone
    # Let's seed entries into Entrance Zone but none into Cosmetics Section
    zones = db_session.query(Zone).filter(Zone.store_id == store_id).all()
    entrance_zone = next(z for z in zones if "Entrance" in z.name)
    cosmetics_zone = next(z for z in zones if "Cosmetics" in z.name)
    
    # Add events in entrance zone
    for i in range(3):
        e = Event(
            event_id=f"evt-ez-{i}", store_id=store_id, event_type="ZONE_ENTER",
            zone_id=entrance_zone.id, timestamp=now - timedelta(minutes=5), visitor_id="visitor-x"
        )
        db_session.add(e)
    db_session.commit()
    
    anomalies = anomaly_service.check_dead_zones(db_session, store_id)
    # Cosmetics Section has 0 entries in the last 30 minutes, should trigger DEAD_ZONE
    dead_zone_alerts = [a for a in anomalies if a.anomaly_type == "DEAD_ZONE" and cosmetics_zone.name in a.message]
    assert len(dead_zone_alerts) > 0

def test_funnel_accuracy(db_session):
    store_id = "store-mumbai-01"
    now = datetime.now(timezone.utc)
    
    zones = db_session.query(Zone).filter(Zone.store_id == store_id).all()
    cosmetics_zone = next(z for z in zones if "Cosmetics" in z.name)
    
    # Visitor 1: ENTRY -> ZONE_VISIT -> BILLING_QUEUE -> PURCHASE
    s1 = VisitorSession(id="sess-fun-1", unique_visitor_id="vis-fun-1", store_id=store_id, start_time=now - timedelta(minutes=30), is_staff=False, converted=True)
    db_session.add(s1)
    
    # Visitor 2: ENTRY -> ZONE_VISIT -> drops off
    s2 = VisitorSession(id="sess-fun-2", unique_visitor_id="vis-fun-2", store_id=store_id, start_time=now - timedelta(minutes=30), is_staff=False, converted=False)
    db_session.add(s2)
    
    # Seed events
    e1 = Event(event_id="e-f1", session_id="sess-fun-1", store_id=store_id, event_type="ZONE_ENTER", zone_id=cosmetics_zone.id, timestamp=now - timedelta(minutes=25), visitor_id="vis-fun-1")
    e2 = Event(event_id="e-f2", session_id="sess-fun-1", store_id=store_id, event_type="BILLING_QUEUE_JOIN", timestamp=now - timedelta(minutes=15), visitor_id="vis-fun-1")
    e3 = Event(event_id="e-f3", session_id="sess-fun-2", store_id=store_id, event_type="ZONE_ENTER", zone_id=cosmetics_zone.id, timestamp=now - timedelta(minutes=25), visitor_id="vis-fun-2")
    
    db_session.add(e1)
    db_session.add(e2)
    db_session.add(e3)
    db_session.commit()
    
    funnel = funnel_service.get_funnel_analytics(db_session, store_id, now - timedelta(hours=1), now)
    stages = {stage["name"]: stage["count"] for stage in funnel["stages"]}
    
    assert stages["ENTRY"] == 2
    assert stages["ZONE_VISIT"] == 2
    assert stages["BILLING_QUEUE"] == 1
    assert stages["PURCHASE"] == 1

def test_heatmap_generation(db_session):
    store_id = "store-mumbai-01"
    now = datetime.now(timezone.utc)
    
    zones = db_session.query(Zone).filter(Zone.store_id == store_id).all()
    cosmetics_zone = next(z for z in zones if "Cosmetics" in z.name)
    
    # Seed visits and dwell times in cosmetics zone
    e1 = Event(event_id="e-hm-1", store_id=store_id, zone_id=cosmetics_zone.id, event_type="ZONE_ENTER", timestamp=now - timedelta(minutes=20), visitor_id="vis-hm")
    # Zone dwell of 120 seconds (120000 ms)
    e2 = Event(event_id="e-hm-2", store_id=store_id, zone_id=cosmetics_zone.id, event_type="ZONE_DWELL", timestamp=now - timedelta(minutes=18), visitor_id="vis-hm", dwell_ms=120000)
    
    db_session.add(e1)
    db_session.add(e2)
    db_session.commit()
    
    heatmap = heatmap_service.get_zone_heatmap(db_session, store_id, now - timedelta(hours=1), now)
    cosmetics_data = next(h for h in heatmap if h["zone_id"] == cosmetics_zone.id)
    
    assert cosmetics_data["visitor_count"] >= 1
    assert cosmetics_data["avg_dwell_time_seconds"] == 120.0
    # Normalized score should be positive and bounded by 100
    assert 0.0 < cosmetics_data["normalized_score"] <= 100.0

def test_health_endpoint(client: TestClient, db_session):
    resp = client.get("/api/v1/health?store_id=store-mumbai-01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "HEALTHY"
    assert "postgres" in data["components"]
    assert "redis" in data["components"]

def test_routes_coverage_stores(client: TestClient, db_session, auth_headers):
    store_id = "store-mumbai-01"
    
    # Heatmap route
    resp = client.get(f"/api/v1/stores/{store_id}/heatmap", headers=auth_headers)
    assert resp.status_code == 200
    
    # Funnel route
    resp = client.get(f"/api/v1/stores/{store_id}/funnel", headers=auth_headers)
    assert resp.status_code == 200

    # Anomalies route
    resp = client.get(f"/api/v1/stores/{store_id}/anomalies", headers=auth_headers)
    assert resp.status_code == 200

    # List stores
    resp = client.get("/api/v1/stores", headers=auth_headers)
    assert resp.status_code == 200
    
    # List cameras
    resp = client.get(f"/api/v1/stores/{store_id}/cameras", headers=auth_headers)
    assert resp.status_code == 200

    # List zones
    resp = client.get(f"/api/v1/stores/{store_id}/zones", headers=auth_headers)
    assert resp.status_code == 200

def test_resolve_anomaly_route(client: TestClient, db_session, auth_headers):
    store_id = "store-mumbai-01"
    
    # Seed anomaly
    anomaly = Anomaly(
        store_id=store_id,
        anomaly_type="DEAD_ZONE",
        severity="Warning",
        message="Zone cosmetics has no traffic",
        timestamp=datetime.now(),
        status="Active"
    )
    db_session.add(anomaly)
    db_session.commit()
    db_session.refresh(anomaly)

    # Resolve anomaly (Admin or Analyst role required, auth_headers is Analyst)
    resp = client.post(
        f"/api/v1/stores/{store_id}/anomalies/{anomaly.id}/resolve?action_taken=checked_layout",
        headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "Resolved"
    assert resp.json()["action_taken"] == "checked_layout"

def test_role_checker_forbidden(client: TestClient):
    # Register and login as Viewer
    client.post(
        "/api/v1/auth/register",
        json={"email": "viewer_test@purplle.com", "password": "viewerpassword", "full_name": "Viewer User", "role": "Viewer"}
    )
    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": "viewer_test@purplle.com", "password": "viewerpassword"}
    )
    token = login_resp.json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {token}"}
    
    # Create store (requires Admin role)
    resp = client.post(
        "/api/v1/stores",
        json={"name": "New Store", "location": "Delhi"},
        headers=viewer_headers
    )
    assert resp.status_code == 403
    assert "permission to access this resource" in resp.json()["detail"]

def test_invalid_token(client: TestClient):
    resp = client.get("/api/v1/stores", headers={"Authorization": "Bearer invalid_token_abc"})
    assert resp.status_code == 401
