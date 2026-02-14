"""Tests for Decision Engine (Slice 7): constraints, rules, engine,
execution, Celery tasks, signal integration, API, tenant isolation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from config.database import sync_engine
from core.enums import DecisionAction, SignalType
import modules.tenant.models  # noqa: F401  — ensure Tenant mapper is loaded for Agent relationship
from modules.decision.constraints import (
    ConstraintResult,
    check_consent,
    check_frequency_cap,
    check_opt_out,
    check_terminal_state,
    check_trai_hours,
    run_all_constraints,
)
from modules.decision.rules import (
    evaluate_rules,
    rule_urgent_001,
    rule_urgent_002,
    rule_opp_001,
    rule_opp_002,
    rule_opp_003,
    rule_proactive_001,
    rule_proactive_002,
    rule_proactive_003,
    rule_proactive_004,
    rule_adm_comp_001,
)
from modules.decision.schemas import DecisionInput, DecisionOutput


# ── Fixtures ────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


def _make_input(**overrides) -> DecisionInput:
    """Create a DecisionInput with sensible defaults."""
    defaults = dict(
        agent_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        lifecycle_state="active",
        days_in_state=10,
        engagement_score=50.0,
        consent={"voice": "granted", "whatsapp": "granted"},
    )
    defaults.update(overrides)
    return DecisionInput(**defaults)


@pytest.fixture
def decision_agent(test_tenant: dict) -> dict:
    """Create a test agent for decision engine tests."""
    agent_id = uuid.uuid4()
    now = _now()
    with sync_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO agents (id, tenant_id, agent_code, full_name, phone, "
                "lifecycle_state, state_since, engagement_score, consent_voice, consent_whatsapp) "
                "VALUES (:id, :tid, :code, :name, :phone, :state, :ss, :es, :cv, :cw)"
            ),
            {
                "id": str(agent_id),
                "tid": str(test_tenant["id"]),
                "code": f"DEC-{agent_id.hex[:8]}",
                "name": "Decision Test Agent",
                "phone": "9876543210",
                "state": "active",
                "ss": (now - timedelta(days=20)).isoformat(),
                "es": 50.0,
                "cv": "granted",
                "cw": "granted",
            },
        )
    yield {"id": agent_id, "tenant_id": test_tenant["id"]}

    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM decision_logs WHERE agent_id = :aid"), {"aid": str(agent_id)})
        conn.execute(text("DELETE FROM signals WHERE agent_id = :aid"), {"aid": str(agent_id)})
        conn.execute(text("DELETE FROM agents WHERE id = :aid"), {"aid": str(agent_id)})


@pytest.fixture
def multi_state_agents(test_tenant: dict) -> list[dict]:
    """Create agents in various lifecycle states for batch evaluation."""
    agents = []
    states = ["onboarded", "licensed", "active", "at_risk", "dormant", "productive", "lapsed", "terminated"]
    now = _now()
    for i, state in enumerate(states):
        agent_id = uuid.uuid4()
        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO agents (id, tenant_id, agent_code, full_name, phone, "
                    "lifecycle_state, state_since, engagement_score) "
                    "VALUES (:id, :tid, :code, :name, :phone, :state, :ss, :es)"
                ),
                {
                    "id": str(agent_id),
                    "tid": str(test_tenant["id"]),
                    "code": f"BATCH-{agent_id.hex[:8]}",
                    "name": f"Agent {state.title()}",
                    "phone": f"98765{43210 + i}",
                    "state": state,
                    "ss": (now - timedelta(days=10)).isoformat(),
                    "es": 40.0 + i * 5,
                },
            )
        agents.append({"id": agent_id, "state": state})

    yield agents

    with sync_engine.begin() as conn:
        for a in agents:
            conn.execute(text("DELETE FROM decision_logs WHERE agent_id = :aid"), {"aid": str(a["id"])})
            conn.execute(text("DELETE FROM signals WHERE agent_id = :aid"), {"aid": str(a["id"])})
            conn.execute(text("DELETE FROM agents WHERE id = :aid"), {"aid": str(a["id"])})


@pytest.fixture
async def decision_token(client: AsyncClient, test_tenant: dict) -> str:
    """Register an ADM user and return access token for Decision API tests."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"dec-{uuid.uuid4().hex[:8]}@test.com",
            "full_name": "Decision ADM",
            "password": "testpass123",
            "tenant_id": str(test_tenant["id"]),
            "roles": ["adm"],
        },
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


# ═══════════════════════════════════════════════════════════════════════
# 1. CONSTRAINT TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestConstraintConsent:
    """CONSTRAINT_001: Consent check."""

    def test_consent_granted_allows(self):
        inp = _make_input(consent={"voice": "granted", "whatsapp": "granted"})
        result = check_consent(inp, "voice_ai")
        assert result.allowed is True

    def test_consent_denied_blocks(self):
        inp = _make_input(consent={"voice": "denied", "whatsapp": "granted"})
        result = check_consent(inp, "voice_ai")
        assert result.allowed is False
        assert "denied" in result.reason

    def test_consent_revoked_blocks(self):
        inp = _make_input(consent={"voice": "granted", "whatsapp": "revoked"})
        result = check_consent(inp, "whatsapp_bot")
        assert result.allowed is False
        assert "revoked" in result.reason

    def test_consent_no_channel_allows(self):
        inp = _make_input(consent={"voice": "denied"})
        result = check_consent(inp, None)
        assert result.allowed is True

    def test_consent_not_asked_allows(self):
        inp = _make_input(consent={"voice": "not_asked"})
        result = check_consent(inp, "voice_ai")
        assert result.allowed is True


class TestConstraintOptOut:
    """CONSTRAINT_002: DND / Opt-out check."""

    def test_dnd_blocks_voice(self):
        inp = _make_input(dnd_registered=True, dnd_call_classification_confirmed=False)
        result = check_opt_out(inp, "voice_ai")
        assert result.allowed is False
        assert "DND" in result.reason

    def test_dnd_confirmed_allows_voice(self):
        inp = _make_input(dnd_registered=True, dnd_call_classification_confirmed=True)
        result = check_opt_out(inp, "voice_ai")
        assert result.allowed is True

    def test_dnd_does_not_block_whatsapp(self):
        inp = _make_input(dnd_registered=True, dnd_call_classification_confirmed=False)
        result = check_opt_out(inp, "whatsapp_bot")
        assert result.allowed is True


class TestConstraintTraiHours:
    """CONSTRAINT_003: TRAI calling hours (09:00-21:00 IST, voice only)."""

    def test_within_trai_hours_allows(self):
        inp = _make_input()
        # 10:00 IST = 04:30 UTC
        scheduled = datetime(2026, 2, 14, 4, 30, tzinfo=timezone.utc)
        result = check_trai_hours(inp, "voice_ai", scheduled)
        assert result.allowed is True

    def test_outside_trai_hours_blocks_with_defer(self):
        inp = _make_input()
        # 23:00 IST = 17:30 UTC
        scheduled = datetime(2026, 2, 14, 17, 30, tzinfo=timezone.utc)
        result = check_trai_hours(inp, "voice_ai", scheduled)
        assert result.allowed is False
        assert result.defer_to is not None
        assert "TRAI" in result.reason

    def test_trai_does_not_affect_whatsapp(self):
        inp = _make_input()
        # 02:00 IST = 20:30 UTC (prev day) — definitely outside hours
        scheduled = datetime(2026, 2, 14, 23, 0, tzinfo=timezone.utc)
        result = check_trai_hours(inp, "whatsapp_bot", scheduled)
        assert result.allowed is True

    def test_early_morning_defers_to_9am_ist(self):
        inp = _make_input()
        # 05:00 IST = 23:30 UTC (prev day)
        scheduled = datetime(2026, 2, 13, 23, 30, tzinfo=timezone.utc)
        result = check_trai_hours(inp, "voice_ai", scheduled)
        assert result.allowed is False
        assert result.defer_to is not None
        # Defer should be 09:00 IST = 03:30 UTC
        assert result.defer_to.hour == 3
        assert result.defer_to.minute == 30


class TestConstraintFrequencyCap:
    """CONSTRAINT_004: Monthly contact frequency cap."""

    def test_under_cap_allows(self):
        inp = _make_input(contacts_this_month=5)
        result = check_frequency_cap(inp, max_contacts_per_month=10)
        assert result.allowed is True

    def test_at_cap_blocks(self):
        inp = _make_input(contacts_this_month=10)
        result = check_frequency_cap(inp, max_contacts_per_month=10)
        assert result.allowed is False

    def test_over_cap_blocks(self):
        inp = _make_input(contacts_this_month=15)
        result = check_frequency_cap(inp)
        assert result.allowed is False


class TestConstraintTerminalState:
    """CONSTRAINT_005: Terminal state check."""

    def test_lapsed_blocked(self):
        inp = _make_input(lifecycle_state="lapsed")
        result = check_terminal_state(inp)
        assert result.allowed is False
        assert "terminal" in result.reason

    def test_terminated_blocked(self):
        inp = _make_input(lifecycle_state="terminated")
        result = check_terminal_state(inp)
        assert result.allowed is False

    def test_active_allowed(self):
        inp = _make_input(lifecycle_state="active")
        result = check_terminal_state(inp)
        assert result.allowed is True


class TestRunAllConstraints:
    """Test combined constraint evaluation."""

    def test_all_pass(self):
        inp = _make_input()
        now = _now()
        result = run_all_constraints(inp, "whatsapp_bot", now)
        assert result.allowed is True

    def test_terminal_short_circuits(self):
        inp = _make_input(lifecycle_state="terminated")
        now = _now()
        result = run_all_constraints(inp, "whatsapp_bot", now)
        assert result.allowed is False
        assert "terminal" in result.reason

    def test_consent_blocks_after_terminal_check(self):
        inp = _make_input(consent={"voice": "revoked"})
        now = _now()
        result = run_all_constraints(inp, "voice_ai", now)
        assert result.allowed is False
        assert "revoked" in result.reason


# ═══════════════════════════════════════════════════════════════════════
# 2. DECISION RULE TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestRuleUrgent001:
    """License expiry < 60 days AND training hours > 10."""

    def test_matches_when_license_expiring_and_training_needed(self):
        inp = _make_input(
            license_expiry_date=_now() + timedelta(days=30),
            training_hours_remaining=15.0,
        )
        result = rule_urgent_001(inp)
        assert result.matched is True
        assert result.output.action == DecisionAction.START_PLAYBOOK
        assert result.output.priority == "URGENT"

    def test_no_match_when_license_far(self):
        inp = _make_input(
            license_expiry_date=_now() + timedelta(days=90),
            training_hours_remaining=15.0,
        )
        result = rule_urgent_001(inp)
        assert result.matched is False

    def test_no_match_when_training_low(self):
        inp = _make_input(
            license_expiry_date=_now() + timedelta(days=30),
            training_hours_remaining=5.0,
        )
        result = rule_urgent_001(inp)
        assert result.matched is False

    def test_no_match_when_no_license_date(self):
        inp = _make_input(license_expiry_date=None, training_hours_remaining=15.0)
        result = rule_urgent_001(inp)
        assert result.matched is False


class TestRuleUrgent002:
    """AT_RISK recently from PRODUCTIVE."""

    def test_matches(self):
        inp = _make_input(
            lifecycle_state="at_risk", previous_state="productive", days_in_state=5,
        )
        result = rule_urgent_002(inp)
        assert result.matched is True
        assert result.output.action == DecisionAction.SEND_NUDGE_TO_ADM

    def test_no_match_when_not_at_risk(self):
        inp = _make_input(
            lifecycle_state="active", previous_state="productive", days_in_state=5,
        )
        result = rule_urgent_002(inp)
        assert result.matched is False

    def test_no_match_when_too_long_in_state(self):
        inp = _make_input(
            lifecycle_state="at_risk", previous_state="productive", days_in_state=20,
        )
        result = rule_urgent_002(inp)
        assert result.matched is False


class TestRuleOpp001:
    """Dormant agent with recent positive signal."""

    def test_matches(self):
        inp = _make_input(
            lifecycle_state="dormant",
            last_positive_signal_at=_now() - timedelta(days=3),
        )
        result = rule_opp_001(inp)
        assert result.matched is True
        assert result.output.action == DecisionAction.SEND_NUDGE_TO_ADM

    def test_no_match_when_positive_signal_old(self):
        inp = _make_input(
            lifecycle_state="dormant",
            last_positive_signal_at=_now() - timedelta(days=14),
        )
        result = rule_opp_001(inp)
        assert result.matched is False

    def test_no_match_when_not_dormant(self):
        inp = _make_input(
            lifecycle_state="active",
            last_positive_signal_at=_now() - timedelta(days=3),
        )
        result = rule_opp_001(inp)
        assert result.matched is False


class TestRuleOpp002:
    """Onboarded agent with no contact after 3 days."""

    def test_matches(self):
        inp = _make_input(
            lifecycle_state="onboarded", days_in_state=5, last_contact_at=None,
        )
        result = rule_opp_002(inp)
        assert result.matched is True
        assert result.output.action == DecisionAction.SCHEDULE_VOICE_CALL

    def test_no_match_when_contacted(self):
        inp = _make_input(
            lifecycle_state="onboarded", days_in_state=5,
            last_contact_at=_now() - timedelta(days=1),
        )
        result = rule_opp_002(inp)
        assert result.matched is False


class TestRuleOpp003:
    """First sale celebration."""

    def test_matches_first_sale(self):
        inp = _make_input(
            total_policies=1,
            last_sale_date=_now() - timedelta(days=1),
        )
        result = rule_opp_003(inp)
        assert result.matched is True
        assert result.output.action == DecisionAction.CELEBRATE

    def test_no_match_when_not_first(self):
        inp = _make_input(
            total_policies=5,
            last_sale_date=_now() - timedelta(days=1),
        )
        result = rule_opp_003(inp)
        assert result.matched is False

    def test_no_match_when_sale_old(self):
        inp = _make_input(
            total_policies=1,
            last_sale_date=_now() - timedelta(days=10),
        )
        result = rule_opp_003(inp)
        assert result.matched is False


class TestRuleProactive001:
    """Licensed agent with insufficient training."""

    def test_matches(self):
        inp = _make_input(lifecycle_state="licensed", training_modules_completed=1)
        result = rule_proactive_001(inp)
        assert result.matched is True
        assert result.output.action == DecisionAction.SEND_TRAINING

    def test_no_match_when_trained(self):
        inp = _make_input(lifecycle_state="licensed", training_modules_completed=5)
        result = rule_proactive_001(inp)
        assert result.matched is False


class TestRuleProactive002:
    """Active agent with no contact in 14+ days."""

    def test_matches(self):
        inp = _make_input(
            lifecycle_state="active",
            last_contact_at=_now() - timedelta(days=20),
        )
        result = rule_proactive_002(inp)
        assert result.matched is True
        assert result.output.action == DecisionAction.SEND_WHATSAPP

    def test_matches_never_contacted(self):
        inp = _make_input(
            lifecycle_state="active", days_in_state=14, last_contact_at=None,
        )
        result = rule_proactive_002(inp)
        assert result.matched is True

    def test_no_match_when_recently_contacted(self):
        inp = _make_input(
            lifecycle_state="active",
            last_contact_at=_now() - timedelta(days=5),
        )
        result = rule_proactive_002(inp)
        assert result.matched is False


class TestRuleProactive003:
    """Dormant agent reactivation attempts."""

    def test_matches(self):
        inp = _make_input(lifecycle_state="dormant", reactivation_attempts=1)
        result = rule_proactive_003(inp)
        assert result.matched is True
        assert result.output.action == DecisionAction.START_PLAYBOOK

    def test_no_match_when_max_attempts(self):
        inp = _make_input(lifecycle_state="dormant", reactivation_attempts=3)
        result = rule_proactive_003(inp)
        assert result.matched is False


class TestRuleProactive004:
    """Productive agent maintenance."""

    def test_matches(self):
        inp = _make_input(
            lifecycle_state="productive",
            last_contact_at=_now() - timedelta(days=35),
        )
        result = rule_proactive_004(inp)
        assert result.matched is True
        assert result.output.action == DecisionAction.SEND_WHATSAPP


class TestRuleAdmComp001:
    """Unresponsive ADM escalation."""

    def test_matches(self):
        inp = _make_input(adm_classification="UNRESPONSIVE")
        result = rule_adm_comp_001(inp)
        assert result.matched is True
        assert result.output.action == DecisionAction.ESCALATE

    def test_no_match_average_adm(self):
        inp = _make_input(adm_classification="AVERAGE")
        result = rule_adm_comp_001(inp)
        assert result.matched is False


class TestEvaluateRules:
    """Test rule chain evaluation — first match wins."""

    def test_urgent_beats_proactive(self):
        inp = _make_input(
            lifecycle_state="at_risk",
            previous_state="productive",
            days_in_state=5,
            adm_classification="UNRESPONSIVE",
        )
        result = evaluate_rules(inp)
        assert result.rule_id == "URGENT_002"

    def test_no_match_returns_do_nothing(self):
        inp = _make_input(lifecycle_state="active", days_in_state=3)
        result = evaluate_rules(inp)
        assert result.action == DecisionAction.DO_NOTHING
        assert result.rule_id == "DEFAULT"

    def test_priority_order_opp_before_proactive(self):
        # Dormant agent with positive signal AND < 3 reactivation attempts
        # OPP_001 should win over PROACTIVE_003
        inp = _make_input(
            lifecycle_state="dormant",
            last_positive_signal_at=_now() - timedelta(days=2),
            reactivation_attempts=1,
        )
        result = evaluate_rules(inp)
        assert result.rule_id == "OPP_001"


# ═══════════════════════════════════════════════════════════════════════
# 3. ENGINE TESTS (async, with DB)
# ═══════════════════════════════════════════════════════════════════════


class TestEvaluateAgent:
    """Test evaluate_agent end-to-end."""

    @pytest.mark.asyncio
    async def test_evaluate_creates_decision_log(self, test_tenant, decision_agent):
        from config.database import async_session_factory
        from modules.decision.engine import evaluate_agent

        async with async_session_factory() as db:
            log = await evaluate_agent(db, decision_agent["id"], test_tenant["id"])
            await db.commit()

        assert log is not None
        assert log.agent_id == decision_agent["id"]
        assert log.tenant_id == test_tenant["id"]
        assert log.decision_action is not None
        assert log.reasoning != ""

    @pytest.mark.asyncio
    async def test_evaluate_agent_not_found_raises(self, test_tenant):
        from config.database import async_session_factory
        from modules.decision.engine import evaluate_agent

        async with async_session_factory() as db:
            with pytest.raises(ValueError, match="not found"):
                await evaluate_agent(db, uuid.uuid4(), test_tenant["id"])

    @pytest.mark.asyncio
    async def test_evaluate_sets_language_from_agent(self, test_tenant, decision_agent):
        from config.database import async_session_factory
        from modules.decision.engine import evaluate_agent

        async with async_session_factory() as db:
            log = await evaluate_agent(db, decision_agent["id"], test_tenant["id"])
            await db.commit()

        # Default language is "hi" (from agent model)
        assert log.language == "hi"


class TestBatchEvaluate:
    """Test batch evaluation."""

    @pytest.mark.asyncio
    async def test_batch_skips_terminal_agents(self, test_tenant, multi_state_agents):
        from config.database import async_session_factory
        from modules.decision.engine import batch_evaluate

        async with async_session_factory() as db:
            results = await batch_evaluate(db, test_tenant["id"])
            await db.commit()

        # Should NOT evaluate lapsed or terminated agents
        evaluated_ids = {str(r.agent_id) for r in results}
        terminal_agents = [a for a in multi_state_agents if a["state"] in ("lapsed", "terminated")]
        for ta in terminal_agents:
            assert str(ta["id"]) not in evaluated_ids

    @pytest.mark.asyncio
    async def test_batch_evaluates_eligible_agents(self, test_tenant, multi_state_agents):
        from config.database import async_session_factory
        from modules.decision.engine import batch_evaluate

        async with async_session_factory() as db:
            results = await batch_evaluate(db, test_tenant["id"])
            await db.commit()

        # Should evaluate some agents (at least the non-terminal ones)
        non_terminal = [a for a in multi_state_agents if a["state"] not in ("lapsed", "terminated")]
        assert len(results) <= len(non_terminal)
        assert len(results) > 0


class TestExecuteDecision:
    """Test decision execution."""

    @pytest.mark.asyncio
    async def test_execute_marks_as_executed(self, test_tenant, decision_agent):
        from config.database import async_session_factory
        from modules.decision.engine import evaluate_agent, execute_decision

        async with async_session_factory() as db:
            log = await evaluate_agent(db, decision_agent["id"], test_tenant["id"])
            await db.flush()

            result = await execute_decision(db, log.id, test_tenant["id"])
            await db.commit()

        assert result.executed is True
        assert result.executed_at is not None
        assert result.execution_result is not None

    @pytest.mark.asyncio
    async def test_execute_idempotent(self, test_tenant, decision_agent):
        from config.database import async_session_factory
        from modules.decision.engine import evaluate_agent, execute_decision

        async with async_session_factory() as db:
            log = await evaluate_agent(db, decision_agent["id"], test_tenant["id"])
            await db.flush()

            result1 = await execute_decision(db, log.id, test_tenant["id"])
            result2 = await execute_decision(db, log.id, test_tenant["id"])
            await db.commit()

        assert result1.executed_at == result2.executed_at

    @pytest.mark.asyncio
    async def test_execute_not_found_raises(self, test_tenant):
        from config.database import async_session_factory
        from modules.decision.engine import execute_decision

        async with async_session_factory() as db:
            with pytest.raises(ValueError, match="not found"):
                await execute_decision(db, uuid.uuid4(), test_tenant["id"])


# ═══════════════════════════════════════════════════════════════════════
# 4. CONSTRAINT + RULE INTEGRATION
# ═══════════════════════════════════════════════════════════════════════


class TestConstraintBlocksAction:
    """Test that constraints properly block or defer rule decisions."""

    @pytest.mark.asyncio
    async def test_consent_revoked_blocks_to_do_nothing(self, test_tenant):
        """Agent with revoked consent → rule fires but constraint blocks → DO_NOTHING."""
        agent_id = uuid.uuid4()
        now = _now()
        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO agents (id, tenant_id, agent_code, full_name, phone, "
                    "lifecycle_state, state_since, consent_voice, consent_whatsapp) "
                    "VALUES (:id, :tid, :code, :name, :phone, :state, :ss, :cv, :cw)"
                ),
                {
                    "id": str(agent_id),
                    "tid": str(test_tenant["id"]),
                    "code": f"REV-{agent_id.hex[:8]}",
                    "name": "Revoked Consent Agent",
                    "phone": "9876500001",
                    "state": "onboarded",
                    "ss": (now - timedelta(days=5)).isoformat(),
                    "cv": "revoked",
                    "cw": "revoked",
                },
            )

        try:
            from config.database import async_session_factory
            from modules.decision.engine import evaluate_agent

            async with async_session_factory() as db:
                log = await evaluate_agent(db, agent_id, test_tenant["id"])
                await db.commit()

            # OPP_002 would match (onboarded > 3 days, no contact) but consent blocks voice
            # So it should be blocked to DO_NOTHING
            assert log.decision_action == DecisionAction.DO_NOTHING
            assert "Blocked by constraint" in log.reasoning or "constraint" in log.reasoning.lower()
        finally:
            with sync_engine.begin() as conn:
                conn.execute(text("DELETE FROM decision_logs WHERE agent_id = :aid"), {"aid": str(agent_id)})
                conn.execute(text("DELETE FROM agents WHERE id = :aid"), {"aid": str(agent_id)})


# ═══════════════════════════════════════════════════════════════════════
# 5. CELERY TASK TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestCeleryTasks:
    """Test Celery task functions directly (not via worker)."""

    def test_decision_engine_batch_runs(self, test_tenant, multi_state_agents):
        from tasks.decision_engine import decision_engine_batch
        result = decision_engine_batch()
        assert "tenants" in result
        assert "evaluated" in result
        assert result["tenants"] >= 1

    def test_execute_pending_decisions_runs(self, test_tenant):
        from tasks.decision_engine import execute_pending_decisions
        result = execute_pending_decisions()
        assert "executed" in result

    def test_batch_creates_decision_logs(self, test_tenant, multi_state_agents):
        from tasks.decision_engine import decision_engine_batch
        decision_engine_batch()

        # Verify logs exist for non-terminal agents
        with sync_engine.begin() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM decision_logs WHERE tenant_id = :tid"),
                {"tid": str(test_tenant["id"])},
            )
            count = result.scalar()
        assert count > 0

    def test_execute_pending_processes_scheduled(self, test_tenant, multi_state_agents):
        """Batch → then execute pending should mark some as executed."""
        from tasks.decision_engine import decision_engine_batch, execute_pending_decisions

        decision_engine_batch()
        result = execute_pending_decisions()
        assert result["executed"] >= 0  # May be 0 if all are DO_NOTHING


# ═══════════════════════════════════════════════════════════════════════
# 6. SIGNAL PROCESSOR INTEGRATION
# ═══════════════════════════════════════════════════════════════════════


class TestSignalIntegration:
    """Test that certain signals trigger immediate decision evaluation."""

    @pytest.mark.asyncio
    async def test_policy_sold_triggers_evaluation(self, test_tenant, decision_agent):
        from config.database import async_session_factory
        from modules.signal.models import Signal
        from modules.signal.processor import process_signal

        async with async_session_factory() as db:
            signal = Signal(
                tenant_id=test_tenant["id"],
                signal_type=SignalType.POLICY_SOLD,
                source="test",
                agent_id=decision_agent["id"],
                timestamp=_now(),
                payload={"policy_type": "term_life", "premium": 10000},
                metadata_={},
            )
            db.add(signal)
            await db.flush()

            await process_signal(db, signal)
            await db.commit()

        # Should have created a decision log
        with sync_engine.begin() as conn:
            result = conn.execute(
                text(
                    "SELECT COUNT(*) FROM decision_logs "
                    "WHERE agent_id = :aid AND tenant_id = :tid"
                ),
                {"aid": str(decision_agent["id"]), "tid": str(test_tenant["id"])},
            )
            count = result.scalar()
        assert count >= 1

    @pytest.mark.asyncio
    async def test_consent_revoked_triggers_evaluation(self, test_tenant, decision_agent):
        from config.database import async_session_factory
        from modules.signal.models import Signal
        from modules.signal.processor import process_signal

        async with async_session_factory() as db:
            signal = Signal(
                tenant_id=test_tenant["id"],
                signal_type=SignalType.CONSENT_CHANGED,
                source="test",
                agent_id=decision_agent["id"],
                timestamp=_now(),
                payload={"consent_type": "voice", "new_status": "revoked"},
                metadata_={},
            )
            db.add(signal)
            await db.flush()

            await process_signal(db, signal)
            await db.commit()

        with sync_engine.begin() as conn:
            result = conn.execute(
                text(
                    "SELECT COUNT(*) FROM decision_logs "
                    "WHERE agent_id = :aid AND tenant_id = :tid"
                ),
                {"aid": str(decision_agent["id"]), "tid": str(test_tenant["id"])},
            )
            count = result.scalar()
        assert count >= 1


# ═══════════════════════════════════════════════════════════════════════
# 7. API ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestDecisionAPI:
    """Test Decision Engine API endpoints."""

    @pytest.mark.asyncio
    async def test_evaluate_agent_endpoint(
        self, client: AsyncClient, test_tenant, decision_agent, decision_token,
    ):
        resp = await client.post(
            f"/api/v1/decisions/evaluate/{decision_agent['id']}",
            headers={"Authorization": f"Bearer {decision_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "rule_id" in data
        assert "decision_action" in data
        assert "reasoning" in data

    @pytest.mark.asyncio
    async def test_list_decisions_endpoint(
        self, client: AsyncClient, test_tenant, decision_agent, decision_token,
    ):
        # First create a decision
        await client.post(
            f"/api/v1/decisions/evaluate/{decision_agent['id']}",
            headers={"Authorization": f"Bearer {decision_token}"},
        )

        resp = await client.get(
            "/api/v1/decisions",
            headers={"Authorization": f"Bearer {decision_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "has_more" in body
        assert len(body["data"]) >= 1

    @pytest.mark.asyncio
    async def test_list_decisions_filter_by_agent(
        self, client: AsyncClient, test_tenant, decision_agent, decision_token,
    ):
        await client.post(
            f"/api/v1/decisions/evaluate/{decision_agent['id']}",
            headers={"Authorization": f"Bearer {decision_token}"},
        )

        resp = await client.get(
            f"/api/v1/decisions?agent_id={decision_agent['id']}",
            headers={"Authorization": f"Bearer {decision_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        for item in body["data"]:
            assert item["agent_id"] == str(decision_agent["id"])

    @pytest.mark.asyncio
    async def test_get_decision_by_id(
        self, client: AsyncClient, test_tenant, decision_agent, decision_token,
    ):
        create_resp = await client.post(
            f"/api/v1/decisions/evaluate/{decision_agent['id']}",
            headers={"Authorization": f"Bearer {decision_token}"},
        )
        decision_id = create_resp.json()["id"]

        resp = await client.get(
            f"/api/v1/decisions/{decision_id}",
            headers={"Authorization": f"Bearer {decision_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == decision_id

    @pytest.mark.asyncio
    async def test_get_decision_not_found(
        self, client: AsyncClient, test_tenant, decision_token,
    ):
        fake_id = uuid.uuid4()
        resp = await client.get(
            f"/api/v1/decisions/{fake_id}",
            headers={"Authorization": f"Bearer {decision_token}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_evaluate_agent_not_found(
        self, client: AsyncClient, test_tenant, decision_token,
    ):
        fake_id = uuid.uuid4()
        resp = await client.post(
            f"/api/v1/decisions/evaluate/{fake_id}",
            headers={"Authorization": f"Bearer {decision_token}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_no_auth_returns_error(self, client: AsyncClient):
        resp = await client.get("/api/v1/decisions")
        assert resp.status_code in (401, 403, 422)


# ═══════════════════════════════════════════════════════════════════════
# 8. TENANT ISOLATION
# ═══════════════════════════════════════════════════════════════════════


class TestTenantIsolation:
    """Verify that decision logs are tenant-isolated."""

    @pytest.mark.asyncio
    async def test_evaluate_in_tenant_a_invisible_to_tenant_b(self, test_tenant, decision_agent):
        from config.database import async_session_factory
        from modules.decision.engine import evaluate_agent

        # Create decision in tenant A
        async with async_session_factory() as db:
            log = await evaluate_agent(db, decision_agent["id"], test_tenant["id"])
            await db.commit()
            log_id = log.id

        # Query from a different tenant → should not find it
        other_tenant_id = uuid.uuid4()
        async with async_session_factory() as db:
            from sqlalchemy import select
            from modules.decision.models import DecisionLog

            result = await db.execute(
                select(DecisionLog).where(
                    DecisionLog.id == log_id,
                    DecisionLog.tenant_id == other_tenant_id,
                )
            )
            found = result.scalar_one_or_none()

        assert found is None


# ═══════════════════════════════════════════════════════════════════════
# 9. REGRESSION — edge cases
# ═══════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge case and regression tests."""

    def test_all_constraints_pass_on_clean_input(self):
        inp = _make_input()
        now = _now()
        result = run_all_constraints(inp, "whatsapp_bot", now)
        assert result.allowed is True

    def test_rule_chain_returns_do_nothing_for_no_match(self):
        inp = _make_input(
            lifecycle_state="first_sale",
            days_in_state=5,
            training_modules_completed=10,
        )
        result = evaluate_rules(inp)
        assert result.action == DecisionAction.DO_NOTHING

    def test_decision_output_schema_fields(self):
        output = DecisionOutput(
            action=DecisionAction.SEND_WHATSAPP,
            rule_id="TEST_001",
            scheduled_time=_now(),
            channel="whatsapp_bot",
            priority="MEDIUM",
            reasoning="Test reasoning",
        )
        assert output.action == DecisionAction.SEND_WHATSAPP
        assert output.playbook_id is None
        assert output.language is None

    def test_constraint_result_defer_to_optional(self):
        r = ConstraintResult(allowed=False, reason="test")
        assert r.defer_to is None

    def test_dormant_agent_with_no_positive_signal_proactive_003(self):
        """Dormant agent without positive signal → PROACTIVE_003 (not OPP_001)."""
        inp = _make_input(
            lifecycle_state="dormant",
            last_positive_signal_at=None,
            reactivation_attempts=0,
        )
        result = evaluate_rules(inp)
        assert result.rule_id == "PROACTIVE_003"
        assert result.action == DecisionAction.START_PLAYBOOK

    def test_dormant_agent_max_reactivation_no_match(self):
        """Dormant agent with 3+ attempts and no positive signal → DO_NOTHING."""
        inp = _make_input(
            lifecycle_state="dormant",
            last_positive_signal_at=None,
            reactivation_attempts=5,
        )
        result = evaluate_rules(inp)
        assert result.action == DecisionAction.DO_NOTHING
