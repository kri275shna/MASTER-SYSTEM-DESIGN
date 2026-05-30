import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta
from app.models.models import Store, Zone, VisitorSession, Event

@pytest.fixture
def auth_header(client: TestClient):
    # Register and login a user to get the JWT token
    client.post(
        "/api/v1/auth/register",
        json={"email": "analyst_test@purplle.com", "password": "password123", "full_name": "Analyst User", "role": "Analyst"}
    )
    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": "analyst_test@purplle.com", "password": "password123"}
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_store_analytics_and_funnel(client: TestClient, db_session, auth_header):
    store_id = "store-mumbai-01"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    # Let's verify we have a zone in Mumbai store
    zone = db_session.query(Zone).filter(Zone.store_id == store_id).first()
    assert zone is not None
    
    # Seed visitor sessions and actions
    # Visitor A: enters, visits zone, joins queue, gets converted (purchased)
    s_a = VisitorSession(id="session-a", unique_visitor_id="visitor-a", store_id=store_id, start_time=now - timedelta(hours=1), is_staff=False, converted=True)
    db_session.add(s_a)
    
    # Visitor B: enters, visits zone, drops off
    s_b = VisitorSession(id="session-b", unique_visitor_id="visitor-b", store_id=store_id, start_time=now - timedelta(minutes=45), is_staff=False, converted=False)
    db_session.add(s_b)
    
    # Staff S: enters, runs tasks (should not count as visitor)
    s_s = VisitorSession(id="session-staff", unique_visitor_id="staff-s", store_id=store_id, start_time=now - timedelta(hours=2), is_staff=True, converted=False)
    db_session.add(s_s)
    
    db_session.commit()
    
    # Seed events for funnel computation
    events = [
        # Visitor A Events
        Event(store_id=store_id, session_id="session-a", event_type="ZONE_ENTER", zone_id=zone.id, timestamp=now - timedelta(minutes=55)),
        Event(store_id=store_id, session_id="session-a", event_type="BILLING_QUEUE_JOIN", timestamp=now - timedelta(minutes=40)),
        # Visitor B Events
        Event(store_id=store_id, session_id="session-b", event_type="ZONE_ENTER", zone_id=zone.id, timestamp=now - timedelta(minutes=40))
    ]
    for e in events:
        db_session.add(e)
    
    # Seed transaction for Visitor A conversion (using query parameters as defined in route)
    client.post(
        f"/api/v1/stores/{store_id}/transactions?session_id=session-a&amount=1499.50&transaction_id=TXN-90234",
        headers=auth_header
    )
    
    # 1. Fetch Metrics
    resp_metrics = client.get(f"/api/v1/stores/{store_id}/metrics", headers=auth_header)
    assert resp_metrics.status_code == 200
    metrics = resp_metrics.json()
    assert metrics["unique_visitors"] == 2 # visitor-a and visitor-b (staff-s excluded)
    assert metrics["converted_visitors"] == 1
    assert metrics["conversion_rate"] == 50.0 # 1 out of 2 visitors
    
    # 2. Fetch Funnel
    resp_funnel = client.get(f"/api/v1/stores/{store_id}/funnel", headers=auth_header)
    assert resp_funnel.status_code == 200
    funnel = resp_funnel.json()
    
    stages = funnel["stages"]
    # ENTRY stage
    assert stages[0]["name"] == "ENTRY"
    assert stages[0]["count"] == 2
    
    # ZONE VISIT stage
    assert stages[1]["name"] == "ZONE_VISIT"
    assert stages[1]["count"] == 2 # both visited the zone
    
    # BILLING QUEUE stage
    assert stages[2]["name"] == "BILLING_QUEUE"
    assert stages[2]["count"] == 1 # only A joined billing
    
    # PURCHASE stage
    assert stages[3]["name"] == "PURCHASE"
    assert stages[3]["count"] == 1 # only A purchased
