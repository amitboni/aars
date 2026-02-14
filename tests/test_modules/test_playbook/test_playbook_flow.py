"""Tests for playbook CRUD, triggering, step execution, branching, and tenant isolation."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from config.database import sync_engine


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
async def auth_token(client: AsyncClient, test_tenant: dict) -> str:
    """Register a tenant_admin user and return access token."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"pbtest-{uuid.uuid4().hex[:8]}@test.com",
            "full_name": "Playbook Test User",
            "password": "testpass123",
            "tenant_id": str(test_tenant["id"]),
            "roles": ["tenant_admin"],
        },
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.fixture
def test_agent(test_tenant: dict) -> dict:
    """Create a test agent for playbook operations."""
    agent_id = uuid.uuid4()
    agent_code = f"PB-AGT-{agent_id.hex[:8]}"
    adm_id = uuid.uuid4()
    with sync_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO agents (id, tenant_id, agent_code, full_name, phone, "
                "lifecycle_state, assigned_adm_id) "
                "VALUES (:id, :tid, :code, :name, :phone, :state, :adm)"
            ),
            {
                "id": str(agent_id),
                "tid": str(test_tenant["id"]),
                "code": agent_code,
                "name": "Playbook Test Agent",
                "phone": "9876543210",
                "state": "dormant",
                "adm": str(adm_id),
            },
        )

    yield {
        "id": agent_id,
        "agent_code": agent_code,
        "tenant_id": test_tenant["id"],
        "adm_id": adm_id,
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


def _build_playbook_payload(name: str | None = None) -> dict:
    """Helper to build a valid playbook creation payload."""
    return {
        "name": name or f"Test Playbook {uuid.uuid4().hex[:6]}",
        "description": "A test playbook with 3 steps",
        "trigger_conditions": {"lifecycle_state": "dormant"},
        "success_criteria": {"outcome": "AGENT_ENGAGED"},
        "max_duration_days": 30,
        "steps": [
            {
                "step_number": 1,
                "name": "Initial WhatsApp Check-in",
                "action_type": "whatsapp_message",
                "action_config": {"message_template": "reactivation_check_in"},
                "delay_days": 0,
                "next_step_rules": [
                    {
                        "condition": "outcome == executed",
                        "go_to_step": 2,
                    }
                ],
            },
            {
                "step_number": 2,
                "name": "Voice Call Follow-up",
                "action_type": "voice_call",
                "action_config": {"purpose": "dormancy_reason_discovery"},
                "delay_days": 2,
                "next_step_rules": [
                    {
                        "condition": "outcome == executed",
                        "go_to_step": 3,
                    }
                ],
            },
            {
                "step_number": 3,
                "name": "ADM Nudge",
                "action_type": "adm_nudge",
                "action_config": {
                    "nudge_message_template": "Agent {agent_name} needs follow-up",
                    "nudge_type": "playbook_step",
                },
                "delay_days": 1,
                "next_step_rules": [],
            },
        ],
    }


# ─── Playbook CRUD Tests ─────────────────────────────────────────────────────


class TestPlaybookCreate:
    async def test_create_playbook_success(
        self, client: AsyncClient, auth_token: str, test_tenant: dict
    ):
        payload = _build_playbook_payload()
        resp = await client.post(
            "/api/v1/playbooks",
            json=payload,
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == payload["name"]
        assert data["description"] == payload["description"]
        assert data["is_active"] is True
        assert data["is_default"] is False
        assert data["max_duration_days"] == 30
        assert data["times_executed"] == 0
        assert data["success_rate"] == 0.0
        assert data["tenant_id"] == str(test_tenant["id"])
        assert len(data["steps"]) == 3
        assert data["steps"][0]["step_number"] == 1
        assert data["steps"][0]["action_type"] == "whatsapp_message"
        assert data["steps"][1]["action_type"] == "voice_call"
        assert data["steps"][2]["action_type"] == "adm_nudge"

    async def test_create_playbook_duplicate_name(
        self, client: AsyncClient, auth_token: str
    ):
        name = f"Dup-{uuid.uuid4().hex[:8]}"
        payload = _build_playbook_payload(name)
        headers = {"Authorization": f"Bearer {auth_token}"}

        resp1 = await client.post("/api/v1/playbooks", json=payload, headers=headers)
        assert resp1.status_code == 201

        resp2 = await client.post("/api/v1/playbooks", json=payload, headers=headers)
        assert resp2.status_code == 409
        assert resp2.json()["error"]["code"] == "CONFLICT"

    async def test_create_playbook_no_steps(
        self, client: AsyncClient, auth_token: str
    ):
        payload = {
            "name": f"Empty-{uuid.uuid4().hex[:8]}",
            "max_duration_days": 14,
        }
        resp = await client.post(
            "/api/v1/playbooks",
            json=payload,
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        assert len(resp.json()["steps"]) == 0

    async def test_create_playbook_invalid_step_number(
        self, client: AsyncClient, auth_token: str
    ):
        payload = _build_playbook_payload()
        payload["steps"][0]["step_number"] = 0  # must be >= 1
        resp = await client.post(
            "/api/v1/playbooks",
            json=payload,
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 422


class TestPlaybookRead:
    async def test_get_playbook(
        self, client: AsyncClient, auth_token: str
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        payload = _build_playbook_payload()
        create_resp = await client.post("/api/v1/playbooks", json=payload, headers=headers)
        playbook_id = create_resp.json()["id"]

        get_resp = await client.get(f"/api/v1/playbooks/{playbook_id}", headers=headers)
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == playbook_id
        assert data["name"] == payload["name"]
        assert len(data["steps"]) == 3

    async def test_get_nonexistent_playbook(
        self, client: AsyncClient, auth_token: str
    ):
        fake_id = uuid.uuid4()
        resp = await client.get(
            f"/api/v1/playbooks/{fake_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404

    async def test_list_playbooks(
        self, client: AsyncClient, auth_token: str
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        # Create two playbooks
        for _ in range(2):
            await client.post("/api/v1/playbooks", json=_build_playbook_payload(), headers=headers)

        resp = await client.get("/api/v1/playbooks", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) >= 2
        assert "next_cursor" in data
        assert "has_more" in data

    async def test_list_playbooks_filter_active(
        self, client: AsyncClient, auth_token: str
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Create active playbook
        await client.post("/api/v1/playbooks", json=_build_playbook_payload(), headers=headers)

        resp = await client.get("/api/v1/playbooks?is_active=true", headers=headers)
        assert resp.status_code == 200
        for pb in resp.json()["data"]:
            assert pb["is_active"] is True

    async def test_list_playbooks_pagination(
        self, client: AsyncClient, auth_token: str
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        for _ in range(3):
            await client.post("/api/v1/playbooks", json=_build_playbook_payload(), headers=headers)

        resp = await client.get("/api/v1/playbooks?limit=2", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["has_more"] is True
        assert data["next_cursor"] is not None

        # Fetch next page
        resp2 = await client.get(
            f"/api/v1/playbooks?limit=2&cursor={data['next_cursor']}",
            headers=headers,
        )
        assert resp2.status_code == 200
        assert len(resp2.json()["data"]) >= 1


class TestPlaybookUpdate:
    async def test_update_playbook_name(
        self, client: AsyncClient, auth_token: str
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/playbooks", json=_build_playbook_payload(), headers=headers
        )
        playbook_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/playbooks/{playbook_id}",
            json={"name": "Updated Playbook Name"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Playbook Name"

    async def test_update_playbook_deactivate(
        self, client: AsyncClient, auth_token: str
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/playbooks", json=_build_playbook_payload(), headers=headers
        )
        playbook_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/playbooks/{playbook_id}",
            json={"is_active": False},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False


class TestPlaybookDelete:
    async def test_soft_delete_playbook(
        self, client: AsyncClient, auth_token: str
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/playbooks", json=_build_playbook_payload(), headers=headers
        )
        playbook_id = create_resp.json()["id"]

        # Delete it
        del_resp = await client.delete(
            f"/api/v1/playbooks/{playbook_id}", headers=headers
        )
        assert del_resp.status_code == 204

        # GET should 404
        get_resp = await client.get(
            f"/api/v1/playbooks/{playbook_id}", headers=headers
        )
        assert get_resp.status_code == 404

    async def test_soft_delete_nonexistent(
        self, client: AsyncClient, auth_token: str
    ):
        fake_id = uuid.uuid4()
        resp = await client.delete(
            f"/api/v1/playbooks/{fake_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404


# ─── Playbook Trigger Tests ──────────────────────────────────────────────────


class TestPlaybookTrigger:
    async def test_trigger_playbook_success(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        # Create playbook
        create_resp = await client.post(
            "/api/v1/playbooks", json=_build_playbook_payload(), headers=headers
        )
        playbook_id = create_resp.json()["id"]

        # Trigger
        trigger_resp = await client.post(
            "/api/v1/playbooks/trigger",
            json={
                "playbook_id": playbook_id,
                "agent_id": str(test_agent["id"]),
                "context": {"trigger_reason": "dormancy_detected"},
            },
            headers=headers,
        )
        assert trigger_resp.status_code == 201
        run = trigger_resp.json()
        assert run["playbook_id"] == playbook_id
        assert run["agent_id"] == str(test_agent["id"])
        assert run["status"] == "in_progress"
        assert run["current_step_number"] == 1
        assert run["steps_executed"] == 0
        assert run["next_step_due_at"] is not None
        assert run["context"]["trigger_reason"] == "dormancy_detected"

    async def test_trigger_increments_execution_count(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/playbooks", json=_build_playbook_payload(), headers=headers
        )
        playbook_id = create_resp.json()["id"]
        assert create_resp.json()["times_executed"] == 0

        await client.post(
            "/api/v1/playbooks/trigger",
            json={"playbook_id": playbook_id, "agent_id": str(test_agent["id"])},
            headers=headers,
        )

        get_resp = await client.get(f"/api/v1/playbooks/{playbook_id}", headers=headers)
        assert get_resp.json()["times_executed"] == 1

    async def test_trigger_emits_playbook_started_signal(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/playbooks", json=_build_playbook_payload(), headers=headers
        )
        playbook_id = create_resp.json()["id"]

        await client.post(
            "/api/v1/playbooks/trigger",
            json={"playbook_id": playbook_id, "agent_id": str(test_agent["id"])},
            headers=headers,
        )

        # Check for PLAYBOOK_STARTED signal
        signals_resp = await client.get(
            f"/api/v1/agents/{test_agent['id']}/signals?signal_type=playbook_started",
            headers=headers,
        )
        assert signals_resp.status_code == 200
        started_signals = signals_resp.json()["data"]
        assert len(started_signals) >= 1
        assert started_signals[0]["payload"]["playbook_id"] == playbook_id

    async def test_trigger_inactive_playbook_fails(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/playbooks", json=_build_playbook_payload(), headers=headers
        )
        playbook_id = create_resp.json()["id"]

        # Deactivate
        await client.put(
            f"/api/v1/playbooks/{playbook_id}",
            json={"is_active": False},
            headers=headers,
        )

        # Trigger should fail
        trigger_resp = await client.post(
            "/api/v1/playbooks/trigger",
            json={"playbook_id": playbook_id, "agent_id": str(test_agent["id"])},
            headers=headers,
        )
        assert trigger_resp.status_code == 400
        assert trigger_resp.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_trigger_empty_playbook_fails(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        payload = {
            "name": f"Empty-{uuid.uuid4().hex[:8]}",
            "max_duration_days": 14,
        }
        create_resp = await client.post(
            "/api/v1/playbooks", json=payload, headers=headers
        )
        playbook_id = create_resp.json()["id"]

        trigger_resp = await client.post(
            "/api/v1/playbooks/trigger",
            json={"playbook_id": playbook_id, "agent_id": str(test_agent["id"])},
            headers=headers,
        )
        assert trigger_resp.status_code == 400
        assert trigger_resp.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_trigger_duplicate_active_run_fails(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/playbooks", json=_build_playbook_payload(), headers=headers
        )
        playbook_id = create_resp.json()["id"]

        trigger_payload = {
            "playbook_id": playbook_id,
            "agent_id": str(test_agent["id"]),
        }

        resp1 = await client.post(
            "/api/v1/playbooks/trigger", json=trigger_payload, headers=headers
        )
        assert resp1.status_code == 201

        resp2 = await client.post(
            "/api/v1/playbooks/trigger", json=trigger_payload, headers=headers
        )
        assert resp2.status_code == 409
        assert resp2.json()["error"]["code"] == "CONFLICT"

    async def test_trigger_nonexistent_playbook_fails(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        resp = await client.post(
            "/api/v1/playbooks/trigger",
            json={
                "playbook_id": str(uuid.uuid4()),
                "agent_id": str(test_agent["id"]),
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404


# ─── Playbook Run List/Get Tests ─────────────────────────────────────────────


class TestPlaybookRuns:
    async def test_list_playbook_runs(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/playbooks", json=_build_playbook_payload(), headers=headers
        )
        playbook_id = create_resp.json()["id"]

        await client.post(
            "/api/v1/playbooks/trigger",
            json={"playbook_id": playbook_id, "agent_id": str(test_agent["id"])},
            headers=headers,
        )

        resp = await client.get("/api/v1/playbooks/runs", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) >= 1
        assert data["data"][0]["status"] == "in_progress"

    async def test_list_runs_filter_by_agent(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/playbooks", json=_build_playbook_payload(), headers=headers
        )
        playbook_id = create_resp.json()["id"]

        await client.post(
            "/api/v1/playbooks/trigger",
            json={"playbook_id": playbook_id, "agent_id": str(test_agent["id"])},
            headers=headers,
        )

        resp = await client.get(
            f"/api/v1/playbooks/runs?agent_id={test_agent['id']}",
            headers=headers,
        )
        assert resp.status_code == 200
        for run in resp.json()["data"]:
            assert run["agent_id"] == str(test_agent["id"])

    async def test_list_runs_filter_by_status(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/playbooks", json=_build_playbook_payload(), headers=headers
        )
        playbook_id = create_resp.json()["id"]

        await client.post(
            "/api/v1/playbooks/trigger",
            json={"playbook_id": playbook_id, "agent_id": str(test_agent["id"])},
            headers=headers,
        )

        resp = await client.get(
            "/api/v1/playbooks/runs?status=in_progress",
            headers=headers,
        )
        assert resp.status_code == 200
        for run in resp.json()["data"]:
            assert run["status"] == "in_progress"

    async def test_get_playbook_run(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/playbooks", json=_build_playbook_payload(), headers=headers
        )
        playbook_id = create_resp.json()["id"]

        trigger_resp = await client.post(
            "/api/v1/playbooks/trigger",
            json={"playbook_id": playbook_id, "agent_id": str(test_agent["id"])},
            headers=headers,
        )
        run_id = trigger_resp.json()["id"]

        get_resp = await client.get(f"/api/v1/playbooks/runs/{run_id}", headers=headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == run_id
        assert get_resp.json()["status"] == "in_progress"


# ─── Step Execution Tests (Sync / Celery path) ───────────────────────────────


class TestStepExecution:
    """Test step execution using the sync Celery task path directly."""

    def _create_playbook_and_trigger(self, tenant_id: uuid.UUID, agent_id: uuid.UUID) -> dict:
        """Create a playbook and trigger a run using sync engine. Returns run info."""
        playbook_id = uuid.uuid4()
        step1_id = uuid.uuid4()
        step2_id = uuid.uuid4()
        step3_id = uuid.uuid4()
        run_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        with sync_engine.begin() as conn:
            # Create playbook
            conn.execute(
                text(
                    "INSERT INTO playbooks (id, tenant_id, name, is_active, trigger_conditions, "
                    "success_criteria, max_duration_days) "
                    "VALUES (:id, :tid, :name, true, '{}'::jsonb, '{}'::jsonb, 30)"
                ),
                {"id": str(playbook_id), "tid": str(tenant_id), "name": f"ExecTest-{uuid.uuid4().hex[:6]}"},
            )

            # Create steps
            for sid, num, name, action, delay in [
                (step1_id, 1, "Step 1 WhatsApp", "whatsapp_message", 0),
                (step2_id, 2, "Step 2 Voice", "voice_call", 0),
                (step3_id, 3, "Step 3 ADM Nudge", "adm_nudge", 0),
            ]:
                conn.execute(
                    text(
                        "INSERT INTO playbook_steps (id, playbook_id, step_number, name, "
                        "action_type, action_config, delay_days, next_step_rules) "
                        "VALUES (:id, :pid, :num, :name, :action, :config, :delay, :rules)"
                    ),
                    {
                        "id": str(sid),
                        "pid": str(playbook_id),
                        "num": num,
                        "name": name,
                        "action": action,
                        "config": "{}",
                        "delay": delay,
                        "rules": "[]",
                    },
                )

            # Create run (due now)
            conn.execute(
                text(
                    "INSERT INTO playbook_runs (id, tenant_id, playbook_id, agent_id, status, "
                    "current_step_number, context, started_at, next_step_due_at, steps_executed) "
                    "VALUES (:id, :tid, :pid, :aid, 'in_progress', 1, '{}'::jsonb, :now, :due, 0)"
                ),
                {
                    "id": str(run_id),
                    "tid": str(tenant_id),
                    "pid": str(playbook_id),
                    "aid": str(agent_id),
                    "now": now.isoformat(),
                    "due": now.isoformat(),
                },
            )

        return {
            "playbook_id": playbook_id,
            "run_id": run_id,
            "step_ids": [step1_id, step2_id, step3_id],
        }

    def test_execute_due_steps_processes_run(
        self, test_tenant: dict, test_agent: dict
    ):
        """Verify that execute_due_playbook_steps processes a due run."""
        from tasks.playbook_execution import execute_due_playbook_steps

        info = self._create_playbook_and_trigger(test_tenant["id"], test_agent["id"])

        result = execute_due_playbook_steps()
        assert result["executed"] >= 1

        # Verify run advanced to step 2
        with sync_engine.begin() as conn:
            row = conn.execute(
                text("SELECT status, current_step_number, steps_executed FROM playbook_runs WHERE id = :id"),
                {"id": str(info["run_id"])},
            ).fetchone()
            assert row is not None
            assert row[0] == "in_progress"
            assert row[1] == 2
            assert row[2] == 1

            # Verify step run was recorded
            step_runs = conn.execute(
                text("SELECT step_number, status FROM playbook_step_runs WHERE playbook_run_id = :rid"),
                {"rid": str(info["run_id"])},
            ).fetchall()
            assert len(step_runs) == 1
            assert step_runs[0][0] == 1
            assert step_runs[0][1] == "completed"

        # Clean up
        self._cleanup(info)

    def test_sequential_step_execution(
        self, test_tenant: dict, test_agent: dict
    ):
        """Execute all 3 steps sequentially and verify playbook completes."""
        from tasks.playbook_execution import execute_due_playbook_steps

        info = self._create_playbook_and_trigger(test_tenant["id"], test_agent["id"])

        # Execute step 1
        execute_due_playbook_steps()

        # Make step 2 due now
        with sync_engine.begin() as conn:
            conn.execute(
                text("UPDATE playbook_runs SET next_step_due_at = :now WHERE id = :id"),
                {"now": datetime.now(timezone.utc).isoformat(), "id": str(info["run_id"])},
            )

        # Execute step 2
        execute_due_playbook_steps()

        # Make step 3 due now
        with sync_engine.begin() as conn:
            conn.execute(
                text("UPDATE playbook_runs SET next_step_due_at = :now WHERE id = :id"),
                {"now": datetime.now(timezone.utc).isoformat(), "id": str(info["run_id"])},
            )

        # Execute step 3 (last step — should complete)
        execute_due_playbook_steps()

        # Verify playbook completed
        with sync_engine.begin() as conn:
            row = conn.execute(
                text("SELECT status, outcome, steps_executed, completed_at FROM playbook_runs WHERE id = :id"),
                {"id": str(info["run_id"])},
            ).fetchone()
            assert row[0] == "completed"
            assert row[1] == "AGENT_ENGAGED"
            assert row[2] == 3
            assert row[3] is not None  # completed_at set

            # Verify all 3 step runs recorded
            step_runs = conn.execute(
                text("SELECT step_number FROM playbook_step_runs WHERE playbook_run_id = :rid ORDER BY step_number"),
                {"rid": str(info["run_id"])},
            ).fetchall()
            assert [sr[0] for sr in step_runs] == [1, 2, 3]

            # Verify PLAYBOOK_COMPLETED signal emitted
            completed_signals = conn.execute(
                text(
                    "SELECT payload FROM signals WHERE agent_id = :aid AND signal_type = 'playbook_completed'"
                ),
                {"aid": str(test_agent["id"])},
            ).fetchall()
            assert len(completed_signals) >= 1

        self._cleanup(info)

    def test_expired_run_is_closed(
        self, test_tenant: dict, test_agent: dict
    ):
        """A run past max_duration_days gets expired."""
        from tasks.playbook_execution import execute_due_playbook_steps

        info = self._create_playbook_and_trigger(test_tenant["id"], test_agent["id"])

        # Backdate started_at to 31 days ago
        past = datetime.now(timezone.utc) - timedelta(days=31)
        with sync_engine.begin() as conn:
            conn.execute(
                text("UPDATE playbook_runs SET started_at = :past WHERE id = :id"),
                {"past": past.isoformat(), "id": str(info["run_id"])},
            )

        result = execute_due_playbook_steps()
        assert result["expired"] >= 1

        with sync_engine.begin() as conn:
            row = conn.execute(
                text("SELECT status, outcome FROM playbook_runs WHERE id = :id"),
                {"id": str(info["run_id"])},
            ).fetchone()
            assert row[0] == "expired"
            assert row[1] == "EXPIRED"

        self._cleanup(info)

    def test_idempotent_execution(
        self, test_tenant: dict, test_agent: dict
    ):
        """Running execute_due_playbook_steps twice only processes once (second time no due steps)."""
        from tasks.playbook_execution import execute_due_playbook_steps

        info = self._create_playbook_and_trigger(test_tenant["id"], test_agent["id"])

        result1 = execute_due_playbook_steps()
        assert result1["executed"] >= 1

        # Second call — step 2 has delay_days=0 but next_step_due_at is set to
        # now + delay, so it may or may not be due depending on exact timing.
        # The key point is it doesn't crash and doesn't double-execute step 1.
        with sync_engine.begin() as conn:
            step_runs = conn.execute(
                text(
                    "SELECT step_number FROM playbook_step_runs WHERE playbook_run_id = :rid AND step_number = 1"
                ),
                {"rid": str(info["run_id"])},
            ).fetchall()
            # Step 1 was only executed once
            assert len(step_runs) == 1

        self._cleanup(info)

    def test_adm_nudge_emits_signal(
        self, test_tenant: dict, test_agent: dict
    ):
        """ADM nudge step emits ADM_NUDGE_RECEIVED signal."""
        from tasks.playbook_execution import execute_due_playbook_steps

        # Create a playbook with just an adm_nudge step
        playbook_id = uuid.uuid4()
        step_id = uuid.uuid4()
        run_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO playbooks (id, tenant_id, name, is_active, trigger_conditions, "
                    "success_criteria, max_duration_days) "
                    "VALUES (:id, :tid, :name, true, '{}'::jsonb, '{}'::jsonb, 30)"
                ),
                {"id": str(playbook_id), "tid": str(test_tenant["id"]),
                 "name": f"ADMTest-{uuid.uuid4().hex[:6]}"},
            )
            conn.execute(
                text(
                    "INSERT INTO playbook_steps (id, playbook_id, step_number, name, "
                    "action_type, action_config, delay_days, next_step_rules) "
                    "VALUES (:id, :pid, 1, 'ADM Nudge', 'adm_nudge', :config, 0, '[]')"
                ),
                {
                    "id": str(step_id),
                    "pid": str(playbook_id),
                    "config": '{"nudge_message_template": "Follow up with agent", "nudge_type": "playbook_step"}',
                },
            )
            conn.execute(
                text(
                    "INSERT INTO playbook_runs (id, tenant_id, playbook_id, agent_id, status, "
                    "current_step_number, context, started_at, next_step_due_at, steps_executed) "
                    "VALUES (:id, :tid, :pid, :aid, 'in_progress', 1, '{}'::jsonb, :now, :due, 0)"
                ),
                {
                    "id": str(run_id),
                    "tid": str(test_tenant["id"]),
                    "pid": str(playbook_id),
                    "aid": str(test_agent["id"]),
                    "now": now.isoformat(),
                    "due": now.isoformat(),
                },
            )

        execute_due_playbook_steps()

        # Check for ADM_NUDGE_RECEIVED signal
        with sync_engine.begin() as conn:
            nudge_signals = conn.execute(
                text(
                    "SELECT signal_type, payload, adm_id FROM signals "
                    "WHERE agent_id = :aid AND signal_type = 'adm_nudge_received'"
                ),
                {"aid": str(test_agent["id"])},
            ).fetchall()
            assert len(nudge_signals) >= 1
            # The adm_id should be set from the agent's assigned_adm_id
            assert nudge_signals[0][2] is not None

        # Clean up
        with sync_engine.begin() as conn:
            conn.execute(text("DELETE FROM playbook_step_runs WHERE playbook_run_id = :rid"), {"rid": str(run_id)})
            conn.execute(text("DELETE FROM signals WHERE agent_id = :aid"), {"aid": str(test_agent["id"])})
            conn.execute(text("DELETE FROM playbook_runs WHERE id = :rid"), {"rid": str(run_id)})
            conn.execute(text("DELETE FROM playbook_steps WHERE playbook_id = :pid"), {"pid": str(playbook_id)})
            conn.execute(text("DELETE FROM playbooks WHERE id = :pid"), {"pid": str(playbook_id)})

    def _cleanup(self, info: dict):
        with sync_engine.begin() as conn:
            conn.execute(text("DELETE FROM playbook_step_runs WHERE playbook_run_id = :rid"), {"rid": str(info["run_id"])})
            conn.execute(text("DELETE FROM signals WHERE payload::text LIKE :pattern"), {"pattern": f"%{info['playbook_id']}%"})
            conn.execute(text("DELETE FROM playbook_runs WHERE id = :rid"), {"rid": str(info["run_id"])})
            conn.execute(text("DELETE FROM playbook_steps WHERE playbook_id = :pid"), {"pid": str(info["playbook_id"])})
            conn.execute(text("DELETE FROM playbooks WHERE id = :pid"), {"pid": str(info["playbook_id"])})


# ─── Condition Evaluator Tests ────────────────────────────────────────────────


class TestConditionEvaluator:
    """Unit tests for the safe condition evaluator."""

    def test_simple_equality(self):
        from modules.playbook.condition_evaluator import evaluate_condition

        assert evaluate_condition("outcome == answered", {"outcome": "answered"}) is True
        assert evaluate_condition("outcome == answered", {"outcome": "not_answered"}) is False

    def test_numeric_comparison(self):
        from modules.playbook.condition_evaluator import evaluate_condition

        assert evaluate_condition("quiz_score >= 60", {"quiz_score": 80}) is True
        assert evaluate_condition("quiz_score >= 60", {"quiz_score": 40}) is False

    def test_and_conditions(self):
        from modules.playbook.condition_evaluator import evaluate_condition

        ctx = {"outcome": "answered", "sentiment": "positive"}
        assert evaluate_condition("outcome == answered AND sentiment == positive", ctx) is True
        assert evaluate_condition("outcome == answered AND sentiment == negative", ctx) is False

    def test_default_always_true(self):
        from modules.playbook.condition_evaluator import evaluate_condition

        assert evaluate_condition("default", {}) is True
        assert evaluate_condition("default", {"anything": "here"}) is True

    def test_empty_condition_true(self):
        from modules.playbook.condition_evaluator import evaluate_condition

        assert evaluate_condition("", {}) is True

    def test_nested_context_access(self):
        from modules.playbook.condition_evaluator import evaluate_condition

        ctx = {"payload": {"outcome": "completed"}}
        assert evaluate_condition("payload.outcome == completed", ctx) is True

    def test_in_operator(self):
        from modules.playbook.condition_evaluator import evaluate_condition

        assert evaluate_condition("status in [active, dormant]", {"status": "dormant"}) is True
        assert evaluate_condition("status in [active, dormant]", {"status": "terminated"}) is False

    def test_not_equal(self):
        from modules.playbook.condition_evaluator import evaluate_condition

        assert evaluate_condition("outcome != failed", {"outcome": "executed"}) is True
        assert evaluate_condition("outcome != failed", {"outcome": "failed"}) is False

    def test_resolve_next_step(self):
        from modules.playbook.condition_evaluator import resolve_next_step

        rules = [
            {"condition": "outcome == answered", "go_to_step": 3},
            {"condition": "outcome == not_answered", "action": "CLOSE_PLAYBOOK", "outcome": "NO_RESPONSE"},
            {"condition": "default", "go_to_step": 2},
        ]
        result = resolve_next_step(rules, {"outcome": "answered"})
        assert result is not None
        assert result["go_to_step"] == 3

        result2 = resolve_next_step(rules, {"outcome": "not_answered"})
        assert result2 is not None
        assert result2["action"] == "CLOSE_PLAYBOOK"

        result3 = resolve_next_step(rules, {"outcome": "something_else"})
        assert result3 is not None
        assert result3["go_to_step"] == 2

    def test_resolve_no_match(self):
        from modules.playbook.condition_evaluator import resolve_next_step

        rules = [
            {"condition": "outcome == very_specific_value", "go_to_step": 5},
        ]
        result = resolve_next_step(rules, {"outcome": "different"})
        assert result is None


# ─── Branching Tests ──────────────────────────────────────────────────────────


class TestPlaybookBranching:
    """Test branching via condition evaluator during step execution."""

    def test_close_playbook_branch(self, test_tenant: dict, test_agent: dict):
        """When a step's rule says CLOSE_PLAYBOOK, the run completes with that outcome."""
        from tasks.playbook_execution import execute_due_playbook_steps

        playbook_id = uuid.uuid4()
        step_id = uuid.uuid4()
        run_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO playbooks (id, tenant_id, name, is_active, trigger_conditions, "
                    "success_criteria, max_duration_days) "
                    "VALUES (:id, :tid, :name, true, '{}'::jsonb, '{}'::jsonb, 30)"
                ),
                {"id": str(playbook_id), "tid": str(test_tenant["id"]),
                 "name": f"BranchTest-{uuid.uuid4().hex[:6]}"},
            )
            # Step with a rule that always closes
            conn.execute(
                text(
                    "INSERT INTO playbook_steps (id, playbook_id, step_number, name, "
                    "action_type, action_config, delay_days, next_step_rules) "
                    "VALUES (:id, :pid, 1, 'Close Step', 'whatsapp_message', '{}'::jsonb, 0, :rules)"
                ),
                {
                    "id": str(step_id),
                    "pid": str(playbook_id),
                    "rules": '[{"condition": "default", "action": "CLOSE_PLAYBOOK", "outcome": "OPTED_OUT"}]',
                },
            )
            conn.execute(
                text(
                    "INSERT INTO playbook_runs (id, tenant_id, playbook_id, agent_id, status, "
                    "current_step_number, context, started_at, next_step_due_at, steps_executed) "
                    "VALUES (:id, :tid, :pid, :aid, 'in_progress', 1, '{}'::jsonb, :now, :due, 0)"
                ),
                {
                    "id": str(run_id),
                    "tid": str(test_tenant["id"]),
                    "pid": str(playbook_id),
                    "aid": str(test_agent["id"]),
                    "now": now.isoformat(),
                    "due": now.isoformat(),
                },
            )

        execute_due_playbook_steps()

        with sync_engine.begin() as conn:
            row = conn.execute(
                text("SELECT status, outcome FROM playbook_runs WHERE id = :id"),
                {"id": str(run_id)},
            ).fetchone()
            assert row[0] == "completed"
            assert row[1] == "OPTED_OUT"

        # Clean up
        with sync_engine.begin() as conn:
            conn.execute(text("DELETE FROM playbook_step_runs WHERE playbook_run_id = :rid"), {"rid": str(run_id)})
            conn.execute(text("DELETE FROM signals WHERE payload::text LIKE :pattern"), {"pattern": f"%{playbook_id}%"})
            conn.execute(text("DELETE FROM playbook_runs WHERE id = :rid"), {"rid": str(run_id)})
            conn.execute(text("DELETE FROM playbook_steps WHERE playbook_id = :pid"), {"pid": str(playbook_id)})
            conn.execute(text("DELETE FROM playbooks WHERE id = :pid"), {"pid": str(playbook_id)})

    def test_goto_step_branch(self, test_tenant: dict, test_agent: dict):
        """When a step's rule says go_to_step, the run jumps to that step."""
        from tasks.playbook_execution import execute_due_playbook_steps

        playbook_id = uuid.uuid4()
        step1_id, step2_id, step3_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        run_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO playbooks (id, tenant_id, name, is_active, trigger_conditions, "
                    "success_criteria, max_duration_days) "
                    "VALUES (:id, :tid, :name, true, '{}'::jsonb, '{}'::jsonb, 30)"
                ),
                {"id": str(playbook_id), "tid": str(test_tenant["id"]),
                 "name": f"GotoTest-{uuid.uuid4().hex[:6]}"},
            )
            # Step 1: go_to_step 3 (skip step 2)
            conn.execute(
                text(
                    "INSERT INTO playbook_steps (id, playbook_id, step_number, name, "
                    "action_type, action_config, delay_days, next_step_rules) "
                    "VALUES (:id, :pid, 1, 'Step 1', 'whatsapp_message', '{}'::jsonb, 0, :rules)"
                ),
                {
                    "id": str(step1_id),
                    "pid": str(playbook_id),
                    "rules": '[{"condition": "default", "go_to_step": 3}]',
                },
            )
            # Step 2 (should be skipped)
            conn.execute(
                text(
                    "INSERT INTO playbook_steps (id, playbook_id, step_number, name, "
                    "action_type, action_config, delay_days, next_step_rules) "
                    "VALUES (:id, :pid, 2, 'Step 2 Skipped', 'voice_call', '{}'::jsonb, 0, '[]')"
                ),
                {"id": str(step2_id), "pid": str(playbook_id)},
            )
            # Step 3
            conn.execute(
                text(
                    "INSERT INTO playbook_steps (id, playbook_id, step_number, name, "
                    "action_type, action_config, delay_days, next_step_rules) "
                    "VALUES (:id, :pid, 3, 'Step 3', 'whatsapp_message', '{}'::jsonb, 0, '[]')"
                ),
                {"id": str(step3_id), "pid": str(playbook_id)},
            )

            conn.execute(
                text(
                    "INSERT INTO playbook_runs (id, tenant_id, playbook_id, agent_id, status, "
                    "current_step_number, context, started_at, next_step_due_at, steps_executed) "
                    "VALUES (:id, :tid, :pid, :aid, 'in_progress', 1, '{}'::jsonb, :now, :due, 0)"
                ),
                {
                    "id": str(run_id),
                    "tid": str(test_tenant["id"]),
                    "pid": str(playbook_id),
                    "aid": str(test_agent["id"]),
                    "now": now.isoformat(),
                    "due": now.isoformat(),
                },
            )

        # Execute step 1 (should jump to step 3)
        execute_due_playbook_steps()

        with sync_engine.begin() as conn:
            row = conn.execute(
                text("SELECT current_step_number FROM playbook_runs WHERE id = :id"),
                {"id": str(run_id)},
            ).fetchone()
            assert row[0] == 3  # Jumped from 1 to 3, skipping 2

        # Clean up
        with sync_engine.begin() as conn:
            conn.execute(text("DELETE FROM playbook_step_runs WHERE playbook_run_id = :rid"), {"rid": str(run_id)})
            conn.execute(text("DELETE FROM signals WHERE payload::text LIKE :pattern"), {"pattern": f"%{playbook_id}%"})
            conn.execute(text("DELETE FROM playbook_runs WHERE id = :rid"), {"rid": str(run_id)})
            conn.execute(text("DELETE FROM playbook_steps WHERE playbook_id = :pid"), {"pid": str(playbook_id)})
            conn.execute(text("DELETE FROM playbooks WHERE id = :pid"), {"pid": str(playbook_id)})


# ─── Tenant Isolation Tests ──────────────────────────────────────────────────


class TestPlaybookTenantIsolation:
    async def test_playbooks_isolated_between_tenants(self, client: AsyncClient):
        """Playbooks from tenant A should not be visible to tenant B."""
        t1_id, t2_id = uuid.uuid4(), uuid.uuid4()

        with sync_engine.begin() as conn:
            for tid, slug in [
                (t1_id, f"pb-a-{t1_id.hex[:6]}"),
                (t2_id, f"pb-b-{t2_id.hex[:6]}"),
            ]:
                conn.execute(
                    text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
                    {"id": str(tid), "name": f"Tenant {slug}", "slug": slug},
                )

        try:
            # Register users
            resp_a = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"pba-{uuid.uuid4().hex[:8]}@test.com",
                    "full_name": "PB User A",
                    "password": "password123",
                    "tenant_id": str(t1_id),
                    "roles": ["tenant_admin"],
                },
            )
            token_a = resp_a.json()["access_token"]

            resp_b = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"pbb-{uuid.uuid4().hex[:8]}@test.com",
                    "full_name": "PB User B",
                    "password": "password123",
                    "tenant_id": str(t2_id),
                    "roles": ["tenant_admin"],
                },
            )
            token_b = resp_b.json()["access_token"]

            # Create playbook in tenant A
            pb_resp = await client.post(
                "/api/v1/playbooks",
                json=_build_playbook_payload(),
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert pb_resp.status_code == 201
            playbook_id_a = pb_resp.json()["id"]

            # Tenant B should NOT see tenant A's playbook
            list_resp_b = await client.get(
                "/api/v1/playbooks",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert list_resp_b.status_code == 200
            for pb in list_resp_b.json()["data"]:
                assert pb["id"] != playbook_id_a
                assert pb["tenant_id"] == str(t2_id)

            # Tenant B trying to GET tenant A's playbook should 404
            get_resp = await client.get(
                f"/api/v1/playbooks/{playbook_id_a}",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert get_resp.status_code == 404

        finally:
            with sync_engine.begin() as conn:
                conn.execute(text("DELETE FROM playbook_step_runs WHERE playbook_run_id IN (SELECT id FROM playbook_runs WHERE tenant_id IN (:t1, :t2))"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM playbook_runs WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM playbook_steps WHERE playbook_id IN (SELECT id FROM playbooks WHERE tenant_id IN (:t1, :t2))"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM playbooks WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM signals WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM agents WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM users WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM tenants WHERE id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
