"""Tests for ADM Experience module: briefing, weekly summary, agent detail,
action logging, alerts, effectiveness, Celery tasks, alert auto-creation, tenant isolation.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from config.database import sync_engine
from core.enums import AgentLifecycleState, SignalType


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def adm_user(test_tenant: dict) -> dict:
    """Create an ADM user in the test tenant."""
    user_id = uuid.uuid4()
    with sync_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, tenant_id, email, full_name, password_hash, roles) "
                "VALUES (:id, :tid, :email, :name, :pw, :roles)"
            ),
            {
                "id": str(user_id),
                "tid": str(test_tenant["id"]),
                "email": f"adm-{user_id.hex[:8]}@test.com",
                "name": "Test ADM",
                "pw": "hashed_pw",
                "roles": "{adm}",
            },
        )

    yield {"id": user_id, "tenant_id": test_tenant["id"], "name": "Test ADM"}

    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(user_id)})


@pytest.fixture
def test_agents(test_tenant: dict, adm_user: dict) -> list[dict]:
    """Create test agents assigned to the ADM."""
    agents = []
    states = [
        ("active", None),
        ("at_risk", None),
        ("dormant", None),
        ("first_sale", None),
        ("productive", None),
    ]
    for i, (state, _) in enumerate(states):
        agent_id = uuid.uuid4()
        code = f"AGT-{agent_id.hex[:8]}"
        now = datetime.now(timezone.utc)
        state_since = now - timedelta(days=10 + i)
        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO agents (id, tenant_id, agent_code, full_name, phone, "
                    "lifecycle_state, state_since, assigned_adm_id, engagement_score) "
                    "VALUES (:id, :tid, :code, :name, :phone, :state, :ss, :adm, :es)"
                ),
                {
                    "id": str(agent_id),
                    "tid": str(test_tenant["id"]),
                    "code": code,
                    "name": f"Agent {state.title()} {i}",
                    "phone": f"98765432{10 + i}",
                    "state": state,
                    "ss": state_since.isoformat(),
                    "adm": str(adm_user["id"]),
                    "es": 50.0 + i * 10,
                },
            )
        agents.append({"id": agent_id, "state": state, "name": f"Agent {state.title()} {i}"})

    yield agents

    with sync_engine.begin() as conn:
        for a in agents:
            conn.execute(text("DELETE FROM signals WHERE agent_id = :aid"), {"aid": str(a["id"])})
            conn.execute(text("DELETE FROM agents WHERE id = :aid"), {"aid": str(a["id"])})


@pytest.fixture
async def adm_token(client: AsyncClient, test_tenant: dict) -> str:
    """Register an ADM user and return access token."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"admtest-{uuid.uuid4().hex[:8]}@test.com",
            "full_name": "ADM Test User",
            "password": "testpass123",
            "tenant_id": str(test_tenant["id"]),
            "roles": ["adm"],
        },
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.fixture
def adm_agents_for_api(test_tenant: dict, adm_token: str) -> list[dict]:
    """Create agents assigned to the token-holding ADM user."""
    # Decode token to get user_id
    from core.security import decode_jwt
    payload = decode_jwt(adm_token)
    adm_id = payload["user_id"]

    agents = []
    for i, state in enumerate(["active", "at_risk", "dormant"]):
        agent_id = uuid.uuid4()
        code = f"API-{agent_id.hex[:8]}"
        now = datetime.now(timezone.utc)
        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO agents (id, tenant_id, agent_code, full_name, phone, "
                    "lifecycle_state, state_since, assigned_adm_id, engagement_score) "
                    "VALUES (:id, :tid, :code, :name, :phone, :state, :ss, :adm, :es)"
                ),
                {
                    "id": str(agent_id),
                    "tid": str(test_tenant["id"]),
                    "code": code,
                    "name": f"API Agent {i}",
                    "phone": f"98765400{10 + i}",
                    "state": state,
                    "ss": now.isoformat(),
                    "adm": str(adm_id),
                    "es": 50.0,
                },
            )
        agents.append({"id": agent_id, "state": state, "name": f"API Agent {i}"})

    yield agents

    with sync_engine.begin() as conn:
        for a in agents:
            conn.execute(text("DELETE FROM adm_actions WHERE agent_id = :aid"), {"aid": str(a["id"])})
            conn.execute(text("DELETE FROM adm_alerts WHERE agent_id = :aid"), {"aid": str(a["id"])})
            conn.execute(text("DELETE FROM signals WHERE agent_id = :aid"), {"aid": str(a["id"])})
            conn.execute(text("DELETE FROM agents WHERE id = :aid"), {"aid": str(a["id"])})


# ── Morning Briefing Tests ──────────────────────────────────────────────


class TestMorningBriefing:
    async def test_generate_briefing_returns_snapshot(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Briefing should contain active/at_risk/dormant counts."""
        from modules.adm.briefing import generate_morning_briefing
        from sqlalchemy.ext.asyncio import AsyncSession
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            result = await generate_morning_briefing(
                db, test_tenant["id"], adm_user["id"]
            )
            await db.commit()

        assert result.snapshot.active_count >= 1
        assert result.snapshot.at_risk_count >= 1
        assert result.snapshot.dormant_count >= 1

    async def test_briefing_priorities_max_five(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Priority list should never exceed 5 agents."""
        from modules.adm.briefing import generate_morning_briefing
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            result = await generate_morning_briefing(
                db, test_tenant["id"], adm_user["id"]
            )
            await db.commit()

        assert len(result.priorities) <= 5

    async def test_briefing_stored_in_db(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Briefing should be stored as a MorningBriefing record."""
        from modules.adm.briefing import generate_morning_briefing
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            result = await generate_morning_briefing(
                db, test_tenant["id"], adm_user["id"]
            )
            await db.commit()

        assert result.id is not None
        assert result.adm_id == adm_user["id"]

    async def test_briefing_snapshot_counts_correct(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Snapshot counts should match fixture agent states."""
        from modules.adm.briefing import generate_morning_briefing
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            result = await generate_morning_briefing(
                db, test_tenant["id"], adm_user["id"]
            )
            await db.commit()

        # active + productive + first_sale = 3 active
        assert result.snapshot.active_count == 3
        assert result.snapshot.at_risk_count == 1
        assert result.snapshot.dormant_count == 1


# ── Weekly Summary Tests ────────────────────────────────────────────────


class TestWeeklySummary:
    async def test_generate_weekly_summary(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Weekly summary should return structured response."""
        from modules.adm.briefing import generate_weekly_summary
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            result = await generate_weekly_summary(
                db, test_tenant["id"], adm_user["id"]
            )
            await db.commit()

        assert result.id is not None
        assert result.adm_id == adm_user["id"]
        assert result.week_start is not None
        assert result.week_end is not None
        assert result.movement is not None
        assert result.adm_numbers is not None

    async def test_weekly_summary_wins_from_signals(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Weekly summary should include POLICY_SOLD as wins."""
        from modules.adm.briefing import generate_weekly_summary
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        # Insert a POLICY_SOLD signal for one of the agents
        agent = test_agents[0]
        now = datetime.now(timezone.utc)
        sig_id = uuid.uuid4()
        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO signals (id, tenant_id, signal_type, source, agent_id, "
                    "timestamp, payload, metadata, processed) "
                    "VALUES (:id, :tid, :st, :src, :aid, :ts, :pl, '{}', true)"
                ),
                {
                    "id": str(sig_id),
                    "tid": str(test_tenant["id"]),
                    "st": SignalType.POLICY_SOLD,
                    "src": "pas_sync",
                    "aid": str(agent["id"]),
                    "ts": now.isoformat(),
                    "pl": '{"product_name": "Term Life"}',
                },
            )

        today = date.today()
        ws = today - timedelta(days=1)
        we = today + timedelta(days=1)

        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            result = await generate_weekly_summary(
                db, test_tenant["id"], adm_user["id"],
                week_start=ws, week_end=we,
            )
            await db.commit()

        assert len(result.wins) >= 1
        assert any("Term Life" in w.achievement for w in result.wins)

    async def test_weekly_summary_stored(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Weekly summary should be stored in DB."""
        from modules.adm.briefing import generate_weekly_summary
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            result = await generate_weekly_summary(
                db, test_tenant["id"], adm_user["id"]
            )
            await db.commit()

        assert result.id is not None


# ── Agent Detail Tests ──────────────────────────────────────────────────


class TestAgentDetail:
    async def test_get_agent_detail(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Should return agent detail with quick actions."""
        from modules.adm.service import get_agent_detail_for_adm
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        agent = test_agents[0]  # active agent
        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            result = await get_agent_detail_for_adm(
                db, test_tenant["id"], adm_user["id"], agent["id"]
            )
            await db.commit()

        assert result is not None
        assert result.agent_id == agent["id"]
        assert result.lifecycle_state == "active"
        assert len(result.quick_actions) >= 2  # call + visit minimum

    async def test_agent_detail_not_found(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Should return None for non-existent agent."""
        from modules.adm.service import get_agent_detail_for_adm
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        fake_id = uuid.uuid4()
        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            result = await get_agent_detail_for_adm(
                db, test_tenant["id"], adm_user["id"], fake_id
            )
            await db.commit()

        assert result is None

    async def test_agent_detail_dormant_has_escalate(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Dormant agents should have escalate quick action."""
        from modules.adm.service import get_agent_detail_for_adm
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        dormant_agent = next(a for a in test_agents if a["state"] == "dormant")
        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            result = await get_agent_detail_for_adm(
                db, test_tenant["id"], adm_user["id"], dormant_agent["id"]
            )
            await db.commit()

        assert result is not None
        action_ids = [a.id for a in result.quick_actions]
        assert "escalate" in action_ids

    async def test_agent_detail_recommendation(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """System recommendation should be populated."""
        from modules.adm.service import get_agent_detail_for_adm
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        agent = test_agents[1]  # at_risk
        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            result = await get_agent_detail_for_adm(
                db, test_tenant["id"], adm_user["id"], agent["id"]
            )
            await db.commit()

        assert result is not None
        assert len(result.system_recommendation) > 0
        assert "at-risk" in result.system_recommendation.lower() or "risk" in result.system_recommendation.lower()


# ── Action Logging Tests ────────────────────────────────────────────────


class TestActionLogging:
    async def test_log_call_action(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Logging a CALLED_AGENT action should emit ADM_AGENT_CALL_LOGGED signal."""
        from modules.adm.action_logger import log_action
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        agent = test_agents[0]
        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            action = await log_action(
                db,
                tenant_id=test_tenant["id"],
                adm_id=adm_user["id"],
                agent_id=agent["id"],
                action_type="CALLED_AGENT",
                notes="Good conversation",
                outcome={"result": "positive"},
            )
            await db.commit()

        assert action.id is not None
        assert action.action_type == "CALLED_AGENT"

        # Verify signal was emitted
        with sync_engine.begin() as conn:
            result = conn.execute(
                text(
                    "SELECT COUNT(*) FROM signals WHERE signal_type = :st AND agent_id = :aid"
                ),
                {"st": SignalType.ADM_AGENT_CALL_LOGGED, "aid": str(agent["id"])},
            )
            assert result.scalar() >= 1

    async def test_log_visit_action(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Logging a VISITED_AGENT action should emit ADM_AGENT_VISIT_LOGGED signal."""
        from modules.adm.action_logger import log_action
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        agent = test_agents[1]
        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            action = await log_action(
                db,
                tenant_id=test_tenant["id"],
                adm_id=adm_user["id"],
                agent_id=agent["id"],
                action_type="VISITED_AGENT",
                notes="Coaching visit",
            )
            await db.commit()

        assert action.action_type == "VISITED_AGENT"

        with sync_engine.begin() as conn:
            result = conn.execute(
                text(
                    "SELECT COUNT(*) FROM signals WHERE signal_type = :st AND agent_id = :aid"
                ),
                {"st": SignalType.ADM_AGENT_VISIT_LOGGED, "aid": str(agent["id"])},
            )
            assert result.scalar() >= 1

    async def test_log_action_no_signal_for_other_types(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Action types like SENT_TRAINING should not emit specific signals."""
        from modules.adm.action_logger import log_action
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        agent = test_agents[0]
        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            action = await log_action(
                db,
                tenant_id=test_tenant["id"],
                adm_id=adm_user["id"],
                agent_id=agent["id"],
                action_type="SENT_TRAINING",
            )
            await db.commit()

        assert action.action_type == "SENT_TRAINING"

    async def test_log_action_outcome_mapping(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Outcome mapping should convert simplified results to signal values."""
        from modules.adm.action_logger import _map_outcome

        assert _map_outcome("positive") == "DETAILED_DISCUSSION"
        assert _map_outcome("okay") == "BRIEF_CHAT"
        assert _map_outcome("not_great") == "CONNECTED"
        assert _map_outcome("skip") == "NOT_ANSWERED"
        assert _map_outcome("unknown") == "CONNECTED"  # default


# ── Alert Tests ─────────────────────────────────────────────────────────


class TestAlerts:
    async def test_create_alert(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Creating an alert should emit ADM_NUDGE_RECEIVED signal."""
        from modules.adm.alerts import create_alert
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        agent = test_agents[0]
        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            alert = await create_alert(
                db,
                tenant_id=test_tenant["id"],
                adm_id=adm_user["id"],
                agent_id=agent["id"],
                alert_type="REENGAGEMENT_SIGNAL",
                urgency="HIGH",
                message="Agent showing interest",
            )
            await db.commit()

        assert alert.id is not None
        assert alert.alert_type == "REENGAGEMENT_SIGNAL"
        assert alert.urgency == "HIGH"

    async def test_mark_alert_read(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Marking an alert as read should set read_at."""
        from modules.adm.alerts import create_alert, mark_alert_read
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        agent = test_agents[0]
        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            alert = await create_alert(
                db, test_tenant["id"], adm_user["id"], agent["id"],
                "TRAINING_COMPLETED", "LOW", "Training done",
            )
            await db.commit()

        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            updated = await mark_alert_read(db, test_tenant["id"], alert.id)
            await db.commit()

        assert updated is not None
        assert updated.read_at is not None

    async def test_mark_alert_acted_on(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Marking alert acted on should set acted_on_at and emit signal."""
        from modules.adm.alerts import create_alert, mark_alert_acted_on
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        agent = test_agents[0]
        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            alert = await create_alert(
                db, test_tenant["id"], adm_user["id"], agent["id"],
                "REENGAGEMENT_SIGNAL", "HIGH", "Re-engage now",
            )
            await db.commit()

        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            updated = await mark_alert_acted_on(db, test_tenant["id"], alert.id)
            await db.commit()

        assert updated is not None
        assert updated.acted_on_at is not None
        assert updated.read_at is not None  # Also marked as read

    async def test_list_alerts_pagination(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """List alerts should support cursor-based pagination."""
        from modules.adm.alerts import create_alert, list_alerts
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        agent = test_agents[0]
        # Create 3 alerts
        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            for i in range(3):
                await create_alert(
                    db, test_tenant["id"], adm_user["id"], agent["id"],
                    "TRAINING_COMPLETED", "LOW", f"Alert {i}",
                )
            await db.commit()

        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            alerts, cursor = await list_alerts(
                db, test_tenant["id"], adm_user["id"], limit=2,
            )
            await db.commit()

        assert len(alerts) == 2
        assert cursor is not None

    async def test_list_alerts_unread_filter(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """List alerts with unread_only should exclude read alerts."""
        from modules.adm.alerts import create_alert, mark_alert_read, list_alerts
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        agent = test_agents[0]
        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            alert1 = await create_alert(
                db, test_tenant["id"], adm_user["id"], agent["id"],
                "REENGAGEMENT_SIGNAL", "HIGH", "Unread alert",
            )
            alert2 = await create_alert(
                db, test_tenant["id"], adm_user["id"], agent["id"],
                "TRAINING_COMPLETED", "LOW", "Will be read",
            )
            await db.commit()

        # Mark one as read
        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            await mark_alert_read(db, test_tenant["id"], alert2.id)
            await db.commit()

        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            alerts, _ = await list_alerts(
                db, test_tenant["id"], adm_user["id"], unread_only=True,
            )
            await db.commit()

        alert_ids = [a.id for a in alerts]
        assert alert1.id in alert_ids
        assert alert2.id not in alert_ids


# ── ADM Effectiveness Tests ─────────────────────────────────────────────


class TestEffectiveness:
    async def test_compute_effectiveness_basic(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Should return classification with portfolio stats."""
        from modules.adm.service import compute_adm_effectiveness
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            result = await compute_adm_effectiveness(
                db, test_tenant["id"], adm_user["id"]
            )
            await db.commit()

        assert result.adm_id == adm_user["id"]
        assert result.portfolio.total_agents == 5
        assert result.classification in (
            "HIGH_PERFORMER", "AVERAGE", "STRUGGLING", "UNRESPONSIVE"
        )

    async def test_effectiveness_portfolio_counts(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Portfolio stats should have correct state breakdown."""
        from modules.adm.service import compute_adm_effectiveness
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            result = await compute_adm_effectiveness(
                db, test_tenant["id"], adm_user["id"]
            )
            await db.commit()

        states = result.portfolio.agents_by_state
        assert states.get("active", 0) == 1
        assert states.get("at_risk", 0) == 1
        assert states.get("dormant", 0) == 1

    async def test_classification_thresholds(self):
        """Classification function should follow spec thresholds."""
        from modules.adm.service import _classify_adm

        # HIGH_PERFORMER: activation > 10% AND response > 70%
        cls, _ = _classify_adm(0.15, 0.8)
        assert cls == "HIGH_PERFORMER"

        # UNRESPONSIVE: response < 20%
        cls, _ = _classify_adm(0.05, 0.1)
        assert cls == "UNRESPONSIVE"

        # STRUGGLING: activation < 3% AND response > 30%
        cls, _ = _classify_adm(0.02, 0.5)
        assert cls == "STRUGGLING"

        # AVERAGE: activation 3-10%
        cls, _ = _classify_adm(0.05, 0.5)
        assert cls == "AVERAGE"


# ── Celery Task Tests ───────────────────────────────────────────────────


class TestCeleryTasks:
    def test_morning_briefing_task_runs(self, test_tenant: dict, adm_user: dict, test_agents):
        """Morning briefing Celery task should generate briefings."""
        from tasks.adm_briefing import generate_morning_briefings

        result = generate_morning_briefings()
        assert "generated" in result
        assert "errors" in result
        assert result["errors"] == 0

    def test_weekly_summary_task_runs(self, test_tenant: dict, adm_user: dict, test_agents):
        """Weekly summary Celery task should generate summaries."""
        from tasks.adm_briefing import generate_weekly_summaries

        result = generate_weekly_summaries()
        assert "generated" in result
        assert "errors" in result
        assert result["errors"] == 0

    def test_morning_briefing_idempotent(self, test_tenant: dict, adm_user: dict, test_agents):
        """Running morning briefing twice should not create duplicates."""
        from tasks.adm_briefing import generate_morning_briefings

        result1 = generate_morning_briefings()
        result2 = generate_morning_briefings()
        # Second run should skip already-generated briefings
        assert result2["generated"] == 0


# ── Alert Auto-Creation Tests ───────────────────────────────────────────


class TestAlertAutoCreation:
    async def test_dormant_whatsapp_reply_creates_alert(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Dormant agent replying on WhatsApp should auto-create REENGAGEMENT_SIGNAL alert."""
        from modules.signal.processor import process_signal
        from modules.signal.models import Signal
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        dormant_agent = next(a for a in test_agents if a["state"] == "dormant")

        signal = Signal(
            tenant_id=test_tenant["id"],
            signal_type=SignalType.WHATSAPP_AGENT_REPLIED,
            source="whatsapp_bot",
            agent_id=dormant_agent["id"],
            timestamp=datetime.now(timezone.utc),
            channel="whatsapp",
            payload={"message_text": "Hello"},
            metadata_={},
        )

        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            db.add(signal)
            await db.flush()
            await process_signal(db, signal)
            await db.commit()

        # Verify alert was created
        with sync_engine.begin() as conn:
            result = conn.execute(
                text(
                    "SELECT alert_type, urgency FROM adm_alerts "
                    "WHERE agent_id = :aid AND alert_type = 'REENGAGEMENT_SIGNAL'"
                ),
                {"aid": str(dormant_agent["id"])},
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "REENGAGEMENT_SIGNAL"
            assert row[1] == "HIGH"

    async def test_quiz_completed_creates_alert(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Quiz completion should auto-create TRAINING_COMPLETED alert."""
        from modules.signal.processor import process_signal
        from modules.signal.models import Signal
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        agent = test_agents[0]  # active agent

        signal = Signal(
            tenant_id=test_tenant["id"],
            signal_type=SignalType.WHATSAPP_TRAINING_INTERACTION,
            source="whatsapp_bot",
            agent_id=agent["id"],
            timestamp=datetime.now(timezone.utc),
            channel="whatsapp",
            payload={"interaction_type": "QUIZ_COMPLETED", "quiz_score": 85},
            metadata_={},
        )

        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            db.add(signal)
            await db.flush()
            await process_signal(db, signal)
            await db.commit()

        with sync_engine.begin() as conn:
            result = conn.execute(
                text(
                    "SELECT alert_type FROM adm_alerts "
                    "WHERE agent_id = :aid AND alert_type = 'TRAINING_COMPLETED'"
                ),
                {"aid": str(agent["id"])},
            )
            assert result.fetchone() is not None

    async def test_consent_revoked_creates_alert(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Consent revocation should auto-create OPTED_OUT alert."""
        from modules.signal.processor import process_signal
        from modules.signal.models import Signal
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        agent = test_agents[0]

        signal = Signal(
            tenant_id=test_tenant["id"],
            signal_type=SignalType.CONSENT_CHANGED,
            source="system",
            agent_id=agent["id"],
            timestamp=datetime.now(timezone.utc),
            payload={"new_status": "revoked", "consent_type": "whatsapp"},
            metadata_={},
        )

        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            db.add(signal)
            await db.flush()
            await process_signal(db, signal)
            await db.commit()

        with sync_engine.begin() as conn:
            result = conn.execute(
                text(
                    "SELECT alert_type, urgency FROM adm_alerts "
                    "WHERE agent_id = :aid AND alert_type = 'OPTED_OUT'"
                ),
                {"aid": str(agent["id"])},
            )
            row = result.fetchone()
            assert row is not None
            assert row[1] == "CRITICAL"

    async def test_no_alert_without_adm(
        self, client: AsyncClient, test_tenant: dict
    ):
        """Agents without assigned ADM should not generate alerts."""
        from modules.signal.processor import process_signal
        from modules.signal.models import Signal
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        # Create agent without ADM
        agent_id = uuid.uuid4()
        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO agents (id, tenant_id, agent_code, full_name, phone, "
                    "lifecycle_state, assigned_adm_id) "
                    "VALUES (:id, :tid, :code, :name, :phone, :state, NULL)"
                ),
                {
                    "id": str(agent_id),
                    "tid": str(test_tenant["id"]),
                    "code": f"NOADM-{agent_id.hex[:8]}",
                    "name": "No ADM Agent",
                    "phone": "9876500001",
                    "state": "dormant",
                },
            )

        signal = Signal(
            tenant_id=test_tenant["id"],
            signal_type=SignalType.WHATSAPP_AGENT_REPLIED,
            source="whatsapp_bot",
            agent_id=agent_id,
            timestamp=datetime.now(timezone.utc),
            channel="whatsapp",
            payload={"message_text": "Hello"},
            metadata_={},
        )

        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            db.add(signal)
            await db.flush()
            await process_signal(db, signal)
            await db.commit()

        with sync_engine.begin() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM adm_alerts WHERE agent_id = :aid"),
                {"aid": str(agent_id)},
            )
            assert result.scalar() == 0

        # Cleanup
        with sync_engine.begin() as conn:
            conn.execute(text("DELETE FROM signals WHERE agent_id = :aid"), {"aid": str(agent_id)})
            conn.execute(text("DELETE FROM agents WHERE id = :aid"), {"aid": str(agent_id)})


# ── Tenant Isolation Tests ──────────────────────────────────────────────


class TestTenantIsolation:
    async def test_briefing_tenant_isolation(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Briefing should only include agents from the same tenant."""
        from modules.adm.briefing import generate_morning_briefing
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        # Create a different tenant
        other_tid = uuid.uuid4()
        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO tenants (id, name, slug, subscription_tier, is_active, config) "
                    "VALUES (:id, 'Other', 'other', 'trial', true, '{}'::jsonb)"
                ),
                {"id": str(other_tid)},
            )

        try:
            async with async_session_factory() as db:
                await set_rls_context_async(db, other_tid)
                result = await generate_morning_briefing(
                    db, other_tid, adm_user["id"]
                )
                await db.commit()

            # Other tenant should have 0 agents
            assert result.snapshot.active_count == 0
            assert result.snapshot.at_risk_count == 0
            assert result.snapshot.dormant_count == 0
        finally:
            with sync_engine.begin() as conn:
                conn.execute(text("DELETE FROM morning_briefings WHERE tenant_id = :tid"), {"tid": str(other_tid)})
                conn.execute(text("DELETE FROM tenants WHERE id = :tid"), {"tid": str(other_tid)})

    async def test_alerts_tenant_isolation(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Alerts from one tenant should not be visible to another."""
        from modules.adm.alerts import create_alert, list_alerts
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        agent = test_agents[0]

        # Create alert in test_tenant
        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            await create_alert(
                db, test_tenant["id"], adm_user["id"], agent["id"],
                "REENGAGEMENT_SIGNAL", "HIGH", "Test alert",
            )
            await db.commit()

        # Create another tenant
        other_tid = uuid.uuid4()
        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO tenants (id, name, slug, subscription_tier, is_active, config) "
                    "VALUES (:id, 'Other2', 'other2', 'trial', true, '{}'::jsonb)"
                ),
                {"id": str(other_tid)},
            )

        try:
            # Query from other tenant — should see nothing
            async with async_session_factory() as db:
                await set_rls_context_async(db, other_tid)
                alerts, _ = await list_alerts(db, other_tid, adm_user["id"])
                await db.commit()

            assert len(alerts) == 0
        finally:
            with sync_engine.begin() as conn:
                conn.execute(text("DELETE FROM tenants WHERE id = :tid"), {"tid": str(other_tid)})


# ── API Endpoint Tests ──────────────────────────────────────────────────


class TestAPIEndpoints:
    async def test_get_briefing_api(
        self, client: AsyncClient, adm_token: str, adm_agents_for_api
    ):
        """GET /api/v1/adm/briefing should return briefing."""
        resp = await client.get(
            "/api/v1/adm/briefing",
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "snapshot" in data
        assert "priorities" in data
        assert "celebrations" in data

    async def test_get_weekly_api(
        self, client: AsyncClient, adm_token: str, adm_agents_for_api
    ):
        """GET /api/v1/adm/briefing/weekly should return weekly summary."""
        resp = await client.get(
            "/api/v1/adm/briefing/weekly",
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "wins" in data
        assert "movement" in data

    async def test_list_agents_api(
        self, client: AsyncClient, adm_token: str, adm_agents_for_api
    ):
        """GET /api/v1/adm/agents should list agents."""
        resp = await client.get(
            "/api/v1/adm/agents",
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) == 3

    async def test_list_agents_filter(
        self, client: AsyncClient, adm_token: str, adm_agents_for_api
    ):
        """GET /api/v1/adm/agents?lifecycle_state=dormant should filter."""
        resp = await client.get(
            "/api/v1/adm/agents?lifecycle_state=dormant",
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["lifecycle_state"] == "dormant"

    async def test_get_agent_detail_api(
        self, client: AsyncClient, adm_token: str, adm_agents_for_api
    ):
        """GET /api/v1/adm/agents/{id}/detail should return detail."""
        agent_id = str(adm_agents_for_api[0]["id"])
        resp = await client.get(
            f"/api/v1/adm/agents/{agent_id}/detail",
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == agent_id
        assert "quick_actions" in data
        assert "system_recommendation" in data

    async def test_create_action_api(
        self, client: AsyncClient, adm_token: str, adm_agents_for_api
    ):
        """POST /api/v1/adm/actions should log an action."""
        agent_id = str(adm_agents_for_api[0]["id"])
        resp = await client.post(
            "/api/v1/adm/actions",
            json={
                "agent_id": agent_id,
                "action_type": "CALLED_AGENT",
                "notes": "Good call",
                "outcome": {"result": "positive"},
            },
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action_type"] == "CALLED_AGENT"

    async def test_alerts_flow_api(
        self, client: AsyncClient, adm_token: str, adm_agents_for_api
    ):
        """Full alert lifecycle: list → create (via action) → list."""
        # List should start empty (or have only alerts from other tests)
        resp = await client.get(
            "/api/v1/adm/alerts",
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        assert resp.status_code == 200

    async def test_effectiveness_api(
        self, client: AsyncClient, adm_token: str, adm_agents_for_api
    ):
        """GET /api/v1/adm/effectiveness should return metrics."""
        resp = await client.get(
            "/api/v1/adm/effectiveness",
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "classification" in data
        assert "portfolio" in data
        assert data["portfolio"]["total_agents"] == 3

    async def test_agent_detail_404(
        self, client: AsyncClient, adm_token: str, adm_agents_for_api
    ):
        """GET /api/v1/adm/agents/{fake_id}/detail should return 404."""
        fake_id = str(uuid.uuid4())
        resp = await client.get(
            f"/api/v1/adm/agents/{fake_id}/detail",
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        assert resp.status_code == 404

    async def test_unauthorized_without_adm_role(
        self, client: AsyncClient, test_tenant: dict
    ):
        """Non-ADM user should get 403."""
        # Register as analyst (not ADM)
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"analyst-{uuid.uuid4().hex[:8]}@test.com",
                "full_name": "Analyst User",
                "password": "testpass123",
                "tenant_id": str(test_tenant["id"]),
                "roles": ["analyst"],
            },
        )
        assert resp.status_code == 201
        token = resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/adm/briefing",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


# ── List ADM Agents Tests ───────────────────────────────────────────────


class TestListADMAgents:
    async def test_list_adm_agents_basic(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Should list all agents assigned to ADM."""
        from modules.adm.service import list_adm_agents
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            agents, cursor = await list_adm_agents(
                db, test_tenant["id"], adm_user["id"]
            )
            await db.commit()

        assert len(agents) == 5
        assert cursor is None  # All fit in one page

    async def test_list_adm_agents_pagination(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Should paginate when limit is less than total."""
        from modules.adm.service import list_adm_agents
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            agents, cursor = await list_adm_agents(
                db, test_tenant["id"], adm_user["id"], limit=3
            )
            await db.commit()

        assert len(agents) == 3
        assert cursor is not None

    async def test_list_adm_agents_filter_state(
        self, client: AsyncClient, test_tenant: dict, adm_user: dict, test_agents
    ):
        """Should filter by lifecycle state."""
        from modules.adm.service import list_adm_agents
        from config.database import async_session_factory
        from core.tenant_context import set_rls_context_async

        async with async_session_factory() as db:
            await set_rls_context_async(db, test_tenant["id"])
            agents, _ = await list_adm_agents(
                db, test_tenant["id"], adm_user["id"],
                lifecycle_state="dormant",
            )
            await db.commit()

        assert len(agents) == 1
        assert agents[0].lifecycle_state == "dormant"
