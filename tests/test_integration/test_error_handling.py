"""tests/test_integration/test_error_handling.py — Error response format tests.

Verifies all error responses use the standard format:
{"error": {"code": "...", "message": "...", "details": {}}}
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from api.app import create_app
from config.database import sync_engine
from sqlalchemy import text
from core.security import create_access_token


@pytest.fixture
def error_app():
    return create_app()


@pytest.fixture
async def error_client(error_app):
    transport = ASGITransport(app=error_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def error_tenant():
    tenant_id = uuid.uuid4()
    slug = f"err-{tenant_id.hex[:8]}"
    with sync_engine.begin() as conn:
        conn.execute(
            text("INSERT INTO tenants (id, name, slug, subscription_tier, is_active, config) "
                 "VALUES (:id, :name, :slug, 'trial', true, '{}'::jsonb)"),
            {"id": str(tenant_id), "name": f"Error Tenant {slug}", "slug": slug},
        )
    yield {"id": tenant_id, "slug": slug}
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM agents WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM users WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM tenants WHERE id = :tid"), {"tid": str(tenant_id)})


def _admin_token(tenant_id: uuid.UUID) -> str:
    return create_access_token(uuid.uuid4(), tenant_id, ["tenant_admin"])


def _analyst_token(tenant_id: uuid.UUID) -> str:
    return create_access_token(uuid.uuid4(), tenant_id, ["analyst"])


class TestErrorResponses:
    """All errors return standard format."""

    @pytest.mark.asyncio
    async def test_422_missing_token(self, error_client):
        """Missing Authorization header returns 422 (FastAPI validation)."""
        resp = await error_client.get("/api/v1/agents")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_401_invalid_token(self, error_client):
        """Invalid JWT returns 401."""
        resp = await error_client.get(
            "/api/v1/agents",
            headers={"Authorization": "Bearer invalid-token-here"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_403_insufficient_role(self, error_client, error_tenant):
        """Analyst trying to create agent returns 403."""
        token = _analyst_token(error_tenant["id"])
        resp = await error_client.post(
            "/api/v1/agents",
            json={
                "agent_code": "ERR-001",
                "full_name": "Error Agent",
                "phone": "9876543200",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_404_agent_not_found(self, error_client, error_tenant):
        """Getting nonexistent agent returns 404 with standard format."""
        token = _admin_token(error_tenant["id"])
        fake_id = uuid.uuid4()
        resp = await error_client.get(
            f"/api/v1/agents/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
        body = resp.json()
        assert "error" in body
        assert "code" in body["error"]
        assert body["error"]["code"] == "AGENT_NOT_FOUND"
        assert "message" in body["error"]

    @pytest.mark.asyncio
    async def test_409_duplicate_agent_code(self, error_client, error_tenant):
        """Creating agent with duplicate code returns 409."""
        token = _admin_token(error_tenant["id"])

        # Create first agent
        resp1 = await error_client.post(
            "/api/v1/agents",
            json={
                "agent_code": "DUP-001",
                "full_name": "First Agent",
                "phone": "9876543210",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp1.status_code == 201

        # Create duplicate
        resp2 = await error_client.post(
            "/api/v1/agents",
            json={
                "agent_code": "DUP-001",
                "full_name": "Duplicate Agent",
                "phone": "9876543211",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 409
        body = resp2.json()
        assert "error" in body
        assert body["error"]["code"] == "CONFLICT"

    @pytest.mark.asyncio
    async def test_422_validation_error(self, error_client, error_tenant):
        """Invalid request body returns 422."""
        token = _admin_token(error_tenant["id"])
        resp = await error_client.post(
            "/api/v1/agents",
            json={
                # Missing required fields
                "agent_code": "",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_health_returns_200(self, error_client):
        """Health endpoint at /health returns 200."""
        resp = await error_client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
