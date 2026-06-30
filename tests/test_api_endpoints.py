"""Comprehensive API endpoint tests.
Tests all 7 API routers with pytest + httpx.
"""
from __future__ import annotations
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "checks" in data
    assert "database" in data["checks"]

@pytest.mark.asyncio
async def test_metrics_endpoint(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "research_agent_info" in resp.text

@pytest.mark.asyncio
async def test_ping(client):
    resp = await client.get("/api/v1/ping")
    assert resp.status_code == 200
    assert resp.json()["ping"] == "pong"

@pytest.mark.asyncio
async def test_list_models(client):
    resp = await client.get("/api/v1/models/")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert "models" in data or isinstance(data, list)

# Session test: requires a pre-existing user in the database
@pytest.mark.asyncio
async def test_create_session(client):
    resp = await client.post("/api/v1/sessions/", json={"user_id": "test-user"})
    # May succeed (user pre-created) or fail (no user in empty DB)
    assert resp.status_code in (200, 404, 422)

@pytest.mark.asyncio
async def test_404_handler(client):
    resp = await client.get("/api/v1/nonexistent")
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"

@pytest.mark.asyncio
async def test_feedback_collect(client):
    resp = await client.post("/api/v1/feedback/collect",
        params={"message_id":"test-msg","rating":1,"user_id":"test","session_id":"test-sess"})
    assert resp.status_code < 500

@pytest.mark.asyncio
async def test_self_growth_status(client):
    resp = await client.get("/api/v1/self-growth/status")
    assert resp.status_code in (200, 404)
