import pytest
import os
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_no_auth(client: AsyncClient):
    """Health endpoint requires no authentication."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_protected_route_no_token(client: AsyncClient):
    """Protected endpoint returns 401 with no token."""
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_invalid_token(client: AsyncClient):
    """Protected endpoint returns 401 with garbage token."""
    resp = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert "error" in body["detail"]


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("TEST_USER_EMAIL"),
    reason="TEST_USER_EMAIL not set — skipping live auth test"
)
async def test_login_valid_credentials(client: AsyncClient):
    """Login with real credentials returns access token."""
    resp = await client.post("/api/v1/auth/login", json={
        "email": os.environ["TEST_USER_EMAIL"],
        "password": os.environ["TEST_USER_PASSWORD"],
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    # Token is non-empty string
    assert len(body["access_token"]) > 50


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    """Login with wrong password returns 401."""
    resp = await client.post("/api/v1/auth/login", json={
        "email": "notexist@example.com",
        "password": "wrongpassword123",
    })
    assert resp.status_code == 401
    body = resp.json()
    assert body["detail"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("TEST_USER_EMAIL"),
    reason="TEST_USER_EMAIL not set — skipping live auth test"
)
async def test_me_endpoint_with_valid_token(client: AsyncClient):
    """GET /users/me returns user data when authenticated."""
    # Login first
    login_resp = await client.post("/api/v1/auth/login", json={
        "email": os.environ["TEST_USER_EMAIL"],
        "password": os.environ["TEST_USER_PASSWORD"],
    })
    token = login_resp.json()["access_token"]

    resp = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "user_id" in body or "id" in body
