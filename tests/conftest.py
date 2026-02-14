"""tests/conftest.py — Shared test fixtures."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from api.app import create_app
from config.database import async_engine, sync_engine


@pytest.fixture(autouse=True)
async def _reset_async_engine():
    """Dispose async engine pool between tests to avoid event loop issues."""
    yield
    await async_engine.dispose()


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def test_tenant() -> dict:
    """Create a unique test tenant using sync engine, clean up after."""
    tenant_id = uuid.uuid4()
    slug = f"test-{tenant_id.hex[:8]}"
    name = f"Test Tenant {slug}"

    with sync_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO tenants (id, name, slug, subscription_tier, is_active, config) "
                "VALUES (:id, :name, :slug, 'trial', true, '{}'::jsonb)"
            ),
            {"id": str(tenant_id), "name": name, "slug": slug},
        )

    yield {"id": tenant_id, "slug": slug, "name": name}

    with sync_engine.begin() as conn:
        # Clean up in dependency order (child tables first)
        conn.execute(text("DELETE FROM integration_jobs WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM analytics_snapshots WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM reactivation_funnels WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM dormancy_analytics WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM decision_logs WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM weekly_summaries WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM adm_alerts WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM adm_actions WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM morning_briefings WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM playbook_step_runs WHERE playbook_run_id IN (SELECT id FROM playbook_runs WHERE tenant_id = :tid)"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM playbook_runs WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM playbook_steps WHERE playbook_id IN (SELECT id FROM playbooks WHERE tenant_id = :tid)"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM playbooks WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM signals WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM agents WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM users WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM tenants WHERE id = :tid"), {"tid": str(tenant_id)})
