"""Tests for signal ingestion, lifecycle transitions, and tenant isolation."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from config.database import sync_engine


@pytest.fixture
def test_agent(test_tenant: dict) -> dict:
    """Create a test agent in the test tenant using sync engine."""
    agent_id = uuid.uuid4()
    agent_code = f"AGT-{agent_id.hex[:8]}"
    with sync_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO agents (id, tenant_id, agent_code, full_name, phone, lifecycle_state) "
                "VALUES (:id, :tid, :code, :name, :phone, :state)"
            ),
            {
                "id": str(agent_id),
                "tid": str(test_tenant["id"]),
                "code": agent_code,
                "name": "Test Agent",
                "phone": "9876543210",
                "state": "licensed",
            },
        )

    yield {
        "id": agent_id,
        "agent_code": agent_code,
        "tenant_id": test_tenant["id"],
    }

    with sync_engine.begin() as conn:
        conn.execute(
            text("DELETE FROM signals WHERE agent_id = :aid"),
            {"aid": str(agent_id)},
        )
        conn.execute(
            text("DELETE FROM agents WHERE id = :aid"),
            {"aid": str(agent_id)},
        )


@pytest.fixture
async def auth_token(client: AsyncClient, test_tenant: dict) -> str:
    """Register a tenant_admin user and return access token."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"sigtest-{uuid.uuid4().hex[:8]}@test.com",
            "full_name": "Signal Test User",
            "password": "testpass123",
            "tenant_id": str(test_tenant["id"]),
            "roles": ["tenant_admin"],
        },
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


class TestSignalEmit:
    async def test_emit_signal_success(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        resp = await client.post(
            "/api/v1/signals",
            json={
                "signal_type": "voice_call_outcome",
                "source": "voice_ai",
                "agent_id": str(test_agent["id"]),
                "payload": {"outcome": "answered", "duration_seconds": 120},
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["created"] is True
        assert data["signal"]["signal_type"] == "voice_call_outcome"
        assert data["signal"]["processed"] is True
        assert data["signal"]["agent_id"] == str(test_agent["id"])

    async def test_emit_signal_idempotency(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        """Duplicate idempotency_key returns existing signal, created=false."""
        idem_key = f"test:{uuid.uuid4().hex}:policy_sold"
        payload = {
            "signal_type": "policy_sold",
            "source": "pas_sync",
            "agent_id": str(test_agent["id"]),
            "payload": {"policy_number": "POL-TEST-001"},
            "idempotency_key": idem_key,
        }

        resp1 = await client.post(
            "/api/v1/signals",
            json=payload,
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp1.status_code == 201
        assert resp1.json()["created"] is True
        signal_id_1 = resp1.json()["signal"]["id"]

        resp2 = await client.post(
            "/api/v1/signals",
            json=payload,
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp2.status_code == 201
        assert resp2.json()["created"] is False
        assert resp2.json()["signal"]["id"] == signal_id_1

    async def test_emit_signal_without_agent(
        self, client: AsyncClient, auth_token: str
    ):
        """Signals can be emitted without an agent_id (system signals)."""
        resp = await client.post(
            "/api/v1/signals",
            json={
                "signal_type": "consent_changed",
                "source": "system",
                "payload": {"channel": "voice_ai", "new_status": "granted"},
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["signal"]["agent_id"] is None


class TestLifecycleTransitions:
    async def test_licensed_to_first_sale(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        """POLICY_SOLD on a licensed agent → first_sale."""
        resp = await client.post(
            "/api/v1/signals",
            json={
                "signal_type": "policy_sold",
                "source": "pas_sync",
                "agent_id": str(test_agent["id"]),
                "payload": {"policy_number": "POL-001", "is_first_sale": True},
                "idempotency_key": f"test:{uuid.uuid4().hex}:pol1",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201

        # Check agent is now first_sale
        agent_resp = await client.get(
            f"/api/v1/agents/{test_agent['id']}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert agent_resp.status_code == 200
        assert agent_resp.json()["lifecycle_state"] == "first_sale"
        assert agent_resp.json()["total_policies_sold"] == 1

    async def test_first_sale_to_active(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        """2 POLICY_SOLD signals → licensed → first_sale → active."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        agent_id = str(test_agent["id"])

        # First sale
        await client.post(
            "/api/v1/signals",
            json={
                "signal_type": "policy_sold",
                "source": "pas_sync",
                "agent_id": agent_id,
                "payload": {"policy_number": "POL-A"},
                "idempotency_key": f"test:{uuid.uuid4().hex}:a",
            },
            headers=headers,
        )
        # Second sale
        await client.post(
            "/api/v1/signals",
            json={
                "signal_type": "policy_sold",
                "source": "pas_sync",
                "agent_id": agent_id,
                "payload": {"policy_number": "POL-B"},
                "idempotency_key": f"test:{uuid.uuid4().hex}:b",
            },
            headers=headers,
        )

        agent_resp = await client.get(
            f"/api/v1/agents/{agent_id}",
            headers=headers,
        )
        assert agent_resp.json()["lifecycle_state"] == "active"
        assert agent_resp.json()["total_policies_sold"] == 2

    async def test_lifecycle_state_changed_signal_emitted(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        """When lifecycle transitions, a lifecycle_state_changed signal is emitted."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        agent_id = str(test_agent["id"])

        await client.post(
            "/api/v1/signals",
            json={
                "signal_type": "policy_sold",
                "source": "pas_sync",
                "agent_id": agent_id,
                "payload": {"policy_number": "POL-C"},
                "idempotency_key": f"test:{uuid.uuid4().hex}:c",
            },
            headers=headers,
        )

        signals_resp = await client.get(
            f"/api/v1/agents/{agent_id}/signals?signal_type=lifecycle_state_changed",
            headers=headers,
        )
        assert signals_resp.status_code == 200
        lsc_signals = signals_resp.json()["data"]
        assert len(lsc_signals) >= 1
        assert lsc_signals[0]["payload"]["previous_state"] == "licensed"
        assert lsc_signals[0]["payload"]["new_state"] == "first_sale"

    async def test_no_transition_for_non_trigger_signal(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        """A non-triggering signal (e.g., whatsapp_message_sent) doesn't change state."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        agent_id = str(test_agent["id"])

        await client.post(
            "/api/v1/signals",
            json={
                "signal_type": "whatsapp_message_sent",
                "source": "whatsapp_bot",
                "agent_id": agent_id,
                "payload": {"message_type": "TEMPLATE"},
            },
            headers=headers,
        )

        agent_resp = await client.get(
            f"/api/v1/agents/{agent_id}",
            headers=headers,
        )
        assert agent_resp.json()["lifecycle_state"] == "licensed"


class TestPositiveSignalTracking:
    async def test_positive_signal_updates_last_positive(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        """A positive signal updates last_positive_signal_at."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        agent_id = str(test_agent["id"])

        # Before: no positive signal
        agent_resp = await client.get(
            f"/api/v1/agents/{agent_id}",
            headers=headers,
        )
        assert agent_resp.json()["last_positive_signal_at"] is None

        # Emit positive signal
        await client.post(
            "/api/v1/signals",
            json={
                "signal_type": "whatsapp_agent_replied",
                "source": "whatsapp_bot",
                "agent_id": agent_id,
                "payload": {"reply_type": "TEXT", "reply_content": "Hello"},
            },
            headers=headers,
        )

        agent_resp = await client.get(
            f"/api/v1/agents/{agent_id}",
            headers=headers,
        )
        assert agent_resp.json()["last_positive_signal_at"] is not None

    async def test_non_positive_signal_does_not_update(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        """A non-positive signal (whatsapp_message_delivered) doesn't update last_positive_signal_at."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        agent_id = str(test_agent["id"])

        await client.post(
            "/api/v1/signals",
            json={
                "signal_type": "whatsapp_message_delivered",
                "source": "whatsapp_bot",
                "agent_id": agent_id,
                "payload": {"message_id": str(uuid.uuid4())},
            },
            headers=headers,
        )

        agent_resp = await client.get(
            f"/api/v1/agents/{agent_id}",
            headers=headers,
        )
        assert agent_resp.json()["last_positive_signal_at"] is None

    async def test_conditional_positive_voice_call_answered(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        """voice_call_outcome with outcome=answered IS positive."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        agent_id = str(test_agent["id"])

        await client.post(
            "/api/v1/signals",
            json={
                "signal_type": "voice_call_outcome",
                "source": "voice_ai",
                "agent_id": agent_id,
                "payload": {"outcome": "answered", "duration_seconds": 60},
            },
            headers=headers,
        )

        agent_resp = await client.get(
            f"/api/v1/agents/{agent_id}",
            headers=headers,
        )
        assert agent_resp.json()["last_positive_signal_at"] is not None
        assert agent_resp.json()["last_contact_at"] is not None

    async def test_conditional_negative_voice_call_not_answered(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        """voice_call_outcome with outcome=not_answered is NOT positive."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        agent_id = str(test_agent["id"])

        await client.post(
            "/api/v1/signals",
            json={
                "signal_type": "voice_call_outcome",
                "source": "voice_ai",
                "agent_id": agent_id,
                "payload": {"outcome": "not_answered"},
            },
            headers=headers,
        )

        agent_resp = await client.get(
            f"/api/v1/agents/{agent_id}",
            headers=headers,
        )
        # Not answered is NOT positive
        assert agent_resp.json()["last_positive_signal_at"] is None
        # But it IS a contact attempt
        assert agent_resp.json()["last_contact_at"] is not None


class TestSignalQuery:
    async def test_list_signals_paginated(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        """List signals with pagination."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        agent_id = str(test_agent["id"])

        # Emit a few signals
        for i in range(3):
            await client.post(
                "/api/v1/signals",
                json={
                    "signal_type": "whatsapp_message_sent",
                    "source": "whatsapp_bot",
                    "agent_id": agent_id,
                    "payload": {"message_type": "TEXT"},
                },
                headers=headers,
            )

        resp = await client.get(
            f"/api/v1/agents/{agent_id}/signals?limit=2",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["has_more"] is True
        assert data["next_cursor"] is not None

    async def test_filter_signals_by_type(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        """Filter signals by signal_type."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        agent_id = str(test_agent["id"])

        await client.post(
            "/api/v1/signals",
            json={
                "signal_type": "whatsapp_message_sent",
                "source": "whatsapp_bot",
                "agent_id": agent_id,
                "payload": {},
            },
            headers=headers,
        )
        await client.post(
            "/api/v1/signals",
            json={
                "signal_type": "policy_sold",
                "source": "pas_sync",
                "agent_id": agent_id,
                "payload": {"policy_number": "POL-F"},
                "idempotency_key": f"test:{uuid.uuid4().hex}:f",
            },
            headers=headers,
        )

        resp = await client.get(
            f"/api/v1/agents/{agent_id}/signals?signal_type=policy_sold",
            headers=headers,
        )
        assert resp.status_code == 200
        for s in resp.json()["data"]:
            assert s["signal_type"] == "policy_sold"


class TestTenantIsolation:
    async def test_signals_isolated_between_tenants(self, client: AsyncClient):
        """Signals from tenant A should not be visible to tenant B."""
        t1_id, t2_id = uuid.uuid4(), uuid.uuid4()

        with sync_engine.begin() as conn:
            for tid, slug in [
                (t1_id, f"sig-a-{t1_id.hex[:6]}"),
                (t2_id, f"sig-b-{t2_id.hex[:6]}"),
            ]:
                conn.execute(
                    text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
                    {"id": str(tid), "name": f"Tenant {slug}", "slug": slug},
                )

        try:
            # Register users in each tenant
            resp_a = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"a-{uuid.uuid4().hex[:8]}@test.com",
                    "full_name": "User A",
                    "password": "password123",
                    "tenant_id": str(t1_id),
                    "roles": ["tenant_admin"],
                },
            )
            token_a = resp_a.json()["access_token"]

            resp_b = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"b-{uuid.uuid4().hex[:8]}@test.com",
                    "full_name": "User B",
                    "password": "password123",
                    "tenant_id": str(t2_id),
                    "roles": ["tenant_admin"],
                },
            )
            token_b = resp_b.json()["access_token"]

            # Create agent in tenant A
            agent_resp = await client.post(
                "/api/v1/agents",
                json={
                    "agent_code": f"ISO-{uuid.uuid4().hex[:6]}",
                    "full_name": "Agent A",
                    "phone": "9876543210",
                },
                headers={"Authorization": f"Bearer {token_a}"},
            )
            agent_a_id = agent_resp.json()["id"]

            # Emit signal for agent A
            await client.post(
                "/api/v1/signals",
                json={
                    "signal_type": "whatsapp_agent_replied",
                    "source": "whatsapp_bot",
                    "agent_id": agent_a_id,
                    "payload": {"reply_type": "TEXT"},
                },
                headers={"Authorization": f"Bearer {token_a}"},
            )

            # Tenant B should see no signals
            signals_b = await client.get(
                "/api/v1/signals",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert signals_b.status_code == 200
            for s in signals_b.json()["data"]:
                assert s["tenant_id"] == str(t2_id)

            # Tenant B should see no agents
            agents_b = await client.get(
                "/api/v1/agents",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert agents_b.status_code == 200
            assert len(agents_b.json()["data"]) == 0

        finally:
            with sync_engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM signals WHERE tenant_id IN (:t1, :t2)"),
                    {"t1": str(t1_id), "t2": str(t2_id)},
                )
                conn.execute(
                    text("DELETE FROM agents WHERE tenant_id IN (:t1, :t2)"),
                    {"t1": str(t1_id), "t2": str(t2_id)},
                )
                conn.execute(
                    text("DELETE FROM users WHERE tenant_id IN (:t1, :t2)"),
                    {"t1": str(t1_id), "t2": str(t2_id)},
                )
                conn.execute(
                    text("DELETE FROM tenants WHERE id IN (:t1, :t2)"),
                    {"t1": str(t1_id), "t2": str(t2_id)},
                )


class TestAgentCRUD:
    async def test_create_agent(
        self, client: AsyncClient, auth_token: str, test_tenant: dict
    ):
        resp = await client.post(
            "/api/v1/agents",
            json={
                "agent_code": f"NEW-{uuid.uuid4().hex[:8]}",
                "full_name": "New Agent",
                "phone": "9123456789",
                "lifecycle_state": "onboarded",
                "preferred_language": "ta",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["full_name"] == "New Agent"
        assert data["lifecycle_state"] == "onboarded"
        assert data["preferred_language"] == "ta"
        assert data["tenant_id"] == str(test_tenant["id"])

    async def test_create_duplicate_agent_code(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        resp = await client.post(
            "/api/v1/agents",
            json={
                "agent_code": test_agent["agent_code"],
                "full_name": "Duplicate",
                "phone": "9111111111",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "CONFLICT"

    async def test_list_agents_with_filters(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}

        resp = await client.get(
            "/api/v1/agents?lifecycle_state=licensed",
            headers=headers,
        )
        assert resp.status_code == 200
        for a in resp.json()["data"]:
            assert a["lifecycle_state"] == "licensed"

    async def test_update_agent(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}

        resp = await client.put(
            f"/api/v1/agents/{test_agent['id']}",
            json={"full_name": "Updated Agent Name", "preferred_language": "en"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Updated Agent Name"
        assert resp.json()["preferred_language"] == "en"
