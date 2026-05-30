import pytest
from fastapi.testclient import TestClient

def test_register_user(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "newuser@purplle.com", "password": "securepassword", "full_name": "Test User", "role": "Viewer"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@purplle.com"
    assert "id" in data
    assert data["role"] == "Viewer"

def test_register_duplicate_email(client: TestClient):
    # First registration
    client.post(
        "/api/v1/auth/register",
        json={"email": "dup@purplle.com", "password": "password", "full_name": "Dup"}
    )
    # Second registration
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "dup@purplle.com", "password": "password", "full_name": "Dup"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"

def test_login_success(client: TestClient):
    # Seed a user
    client.post(
        "/api/v1/auth/register",
        json={"email": "login@purplle.com", "password": "my-password", "full_name": "Login User"}
    )
    
    # Login via OAuth2 Form
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "login@purplle.com", "password": "my-password"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "Viewer"

def test_login_failure(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "login@purplle.com", "password": "wrong-password"}
    )
    assert response.status_code == 401

def test_get_me(client: TestClient):
    # Register and login
    client.post(
        "/api/v1/auth/register",
        json={"email": "me@purplle.com", "password": "password", "full_name": "Me User"}
    )
    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": "me@purplle.com", "password": "password"}
    )
    token = login_resp.json()["access_token"]
    
    # Fetch details
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "me@purplle.com"
