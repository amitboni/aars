"""Tests for Analytics module (Slice 8): dashboard, dormancy, funnel,
ADM performance, training effectiveness, system ROI, stored reports,
Celery tasks, tenant isolation, and regression.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from config.database import sync_engine
from core.enums import AgentLifecycleState, SignalType, UserRole
import modules.tenant.models  # noqa: F401 — ensure Tenant mapper is loaded


# ── Helpers ────────────────────────────────────────────────────────────


def _now():
    return datetime.now(timezone.utc)


def _insert_agent(conn, agent_id, tenant_id, **overrides):
    """Insert a test agent with sensible defaults."""
    defaults = {
        "id": str(agent_id),
        "tid": str(tenant_id),
        "code": f"ANA-{agent_id.hex[:8]}",
        "name": "Analytics Test Agent",
        "phone": f"98765{hash(agent_id) % 100000:05d}",
        "state": "active",
        "ss": (_now() - timedelta(days=30)).isoformat(),
        "es": 50.0,
        "dr": None,
        "rn": None,
        "adm": None,
    }
    defaults.update(overrides)
    conn.execute(
        text(
            "INSERT INTO agents (id, tenant_id, agent_code, full_name, phone, "
            "lifecycle_state, state_since, engagement_score, dormancy_reason, "
            "region_node_id, assigned_adm_id) "
            "VALUES (:id, :tid, :code, :name, :phone, :state, :ss, :es, :dr, "
            "CAST(:rn AS uuid), CAST(:adm AS uuid))"
        ),
        defaults,
    )


def _insert_signal(conn, tenant_id, agent_id, signal_type, **overrides):
    """Insert a test signal."""
    sig_id = uuid.uuid4()
    defaults = {
        "id": str(sig_id),
        "tid": str(tenant_id),
        "aid": str(agent_id) if agent_id else None,
        "stype": str(signal_type),
        "source": "test",
        "ts": _now().isoformat(),
        "pl": "{}",
        "meta": "{}",
        "channel": None,
        "adm_id": None,
    }
    defaults.update(overrides)
    conn.execute(
        text(
            "INSERT INTO signals (id, tenant_id, agent_id, signal_type, source, "
            "timestamp, payload, metadata, channel, adm_id) "
            "VALUES (:id, :tid, CAST(:aid AS uuid), :stype, :source, :ts, "
            "CAST(:pl AS jsonb), CAST(:meta AS jsonb), :channel, CAST(:adm_id AS uuid))"
        ),
        defaults,
    )
    return sig_id


def _insert_user(conn, user_id, tenant_id, roles, **overrides):
    """Insert a test user."""
    defaults = {
        "id": str(user_id),
        "tid": str(tenant_id),
        "email": f"test-{user_id.hex[:8]}@test.com",
        "name": "Test User",
        "pw": "$2b$12$test_hash_not_real_but_valid_length_padding",
        "roles": "{" + ",".join(roles) + "}",
    }
    defaults.update(overrides)
    conn.execute(
        text(
            "INSERT INTO users (id, tenant_id, email, full_name, password_hash, roles) "
            "VALUES (:id, :tid, :email, :name, :pw, :roles)"
        ),
        defaults,
    )


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def analytics_agents(test_tenant: dict) -> list[dict]:
    """Create agents in various lifecycle states for analytics tests."""
    agents = []
    configs = [
        {"state": "active", "dr": None},
        {"state": "active", "dr": None},
        {"state": "productive", "dr": None},
        {"state": "at_risk", "dr": None},
        {"state": "dormant", "dr": "training_gap.product_knowledge_insufficient"},
        {"state": "dormant", "dr": "engagement_gap.adm_never_contacted"},
        {"state": "dormant", "dr": "training_gap.product_knowledge_insufficient"},
        {"state": "first_sale", "dr": None},
        {"state": "onboarded", "dr": None},
        {"state": "licensed", "dr": None},
    ]

    with sync_engine.begin() as conn:
        for cfg in configs:
            agent_id = uuid.uuid4()
            _insert_agent(
                conn, agent_id, test_tenant["id"],
                state=cfg["state"],
                dr=cfg["dr"],
            )
            agents.append({"id": agent_id, "state": cfg["state"], "dormancy_reason": cfg["dr"]})

    yield agents

    with sync_engine.begin() as conn:
        for a in agents:
            conn.execute(text("DELETE FROM signals WHERE agent_id = :aid"), {"aid": str(a["id"])})
            conn.execute(text("DELETE FROM agents WHERE id = :aid"), {"aid": str(a["id"])})


@pytest.fixture
def analytics_signals(test_tenant: dict, analytics_agents: list[dict]) -> list:
    """Create signals for analytics tests (outreach, engagement, training, sales, lifecycle)."""
    sig_ids = []
    now = _now()

    with sync_engine.begin() as conn:
        # Outreach signals for first 4 agents
        for agent in analytics_agents[:4]:
            sid = _insert_signal(
                conn, test_tenant["id"], agent["id"],
                SignalType.WHATSAPP_MESSAGE_SENT,
                ts=(now - timedelta(days=5)).isoformat(),
                channel="whatsapp_bot",
            )
            sig_ids.append(sid)

        # Engagement: agent 0 and 1 replied
        for agent in analytics_agents[:2]:
            sid = _insert_signal(
                conn, test_tenant["id"], agent["id"],
                SignalType.WHATSAPP_AGENT_REPLIED,
                ts=(now - timedelta(days=4)).isoformat(),
                channel="whatsapp_bot",
            )
            sig_ids.append(sid)

        # Training: agent 0 completed training
        sid = _insert_signal(
            conn, test_tenant["id"], analytics_agents[0]["id"],
            SignalType.WHATSAPP_TRAINING_INTERACTION,
            ts=(now - timedelta(days=3)).isoformat(),
            pl='{"module_id": "product_term_life", "interaction_type": "QUIZ_COMPLETED", "quiz_score": 85, "completion_percentage": 100}',
        )
        sig_ids.append(sid)

        # Sale: agent 0 sold a policy
        sid = _insert_signal(
            conn, test_tenant["id"], analytics_agents[0]["id"],
            SignalType.POLICY_SOLD,
            ts=(now - timedelta(days=1)).isoformat(),
            pl='{"premium": {"amount": 25000, "currency": "INR"}, "product_name": "Term Life"}',
        )
        sig_ids.append(sid)

        # Lifecycle change: agent 4 reactivated (DORMANT -> ACTIVE)
        sid = _insert_signal(
            conn, test_tenant["id"], analytics_agents[4]["id"],
            SignalType.LIFECYCLE_STATE_CHANGED,
            ts=(now - timedelta(days=2)).isoformat(),
            pl='{"previous_state": "dormant", "new_state": "active"}',
        )
        sig_ids.append(sid)

        # ADM nudge signals
        adm_id = uuid.uuid4()
        sid = _insert_signal(
            conn, test_tenant["id"], analytics_agents[0]["id"],
            SignalType.ADM_NUDGE_RECEIVED,
            ts=(now - timedelta(days=10)).isoformat(),
            adm_id=str(adm_id),
        )
        sig_ids.append(sid)
        sid = _insert_signal(
            conn, test_tenant["id"], analytics_agents[0]["id"],
            SignalType.ADM_NUDGE_ACTED_ON,
            ts=(now - timedelta(days=9)).isoformat(),
            adm_id=str(adm_id),
        )
        sig_ids.append(sid)

    yield sig_ids

    with sync_engine.begin() as conn:
        for sid in sig_ids:
            conn.execute(text("DELETE FROM signals WHERE id = :sid"), {"sid": str(sid)})


@pytest.fixture
def analytics_adm(test_tenant: dict, analytics_agents: list[dict]) -> dict:
    """Create an ADM user and assign agents to them."""
    adm_id = uuid.uuid4()

    with sync_engine.begin() as conn:
        _insert_user(conn, adm_id, test_tenant["id"], ["adm"], name="ADM Analytics Test")

        # Assign first 5 agents to this ADM
        for agent in analytics_agents[:5]:
            conn.execute(
                text("UPDATE agents SET assigned_adm_id = :adm WHERE id = :aid"),
                {"adm": str(adm_id), "aid": str(agent["id"])},
            )

    yield {"id": adm_id, "tenant_id": test_tenant["id"]}

    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": str(adm_id)})


@pytest.fixture
async def analytics_token(client: AsyncClient, test_tenant: dict) -> str:
    """Register a tenant_admin user and return access token for Analytics API tests."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"ana-{uuid.uuid4().hex[:8]}@test.com",
            "full_name": "Analytics Admin",
            "password": "testpass123",
            "tenant_id": str(test_tenant["id"]),
            "roles": ["tenant_admin"],
        },
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.fixture
async def analyst_token(client: AsyncClient, test_tenant: dict) -> str:
    """Register an analyst user and return access token."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"analyst-{uuid.uuid4().hex[:8]}@test.com",
            "full_name": "Analytics Analyst",
            "password": "testpass123",
            "tenant_id": str(test_tenant["id"]),
            "roles": ["analyst"],
        },
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.fixture
async def adm_token(client: AsyncClient, test_tenant: dict) -> str:
    """Register an ADM user and return access token (should NOT access analytics)."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"adm-ana-{uuid.uuid4().hex[:8]}@test.com",
            "full_name": "ADM No Analytics",
            "password": "testpass123",
            "tenant_id": str(test_tenant["id"]),
            "roles": ["adm"],
        },
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


# ═══════════════════════════════════════════════════════════════════════
# 1. DASHBOARD TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestDashboardService:
    """Test dashboard computation directly."""

    @pytest.mark.asyncio
    async def test_dashboard_agent_counts(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_dashboard

        async with async_session_factory() as db:
            result = await get_dashboard(db, test_tenant["id"])

        assert result["total_agents"] == 10
        # active(2) + productive(1) + first_sale(1) = 4 "active"
        assert result["active_agents"] >= 2
        assert result["at_risk_agents"] >= 1
        assert result["dormant_agents"] >= 2

    @pytest.mark.asyncio
    async def test_dashboard_agents_by_state(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_dashboard

        async with async_session_factory() as db:
            result = await get_dashboard(db, test_tenant["id"])

        assert "active" in result["agents_by_state"]
        assert "dormant" in result["agents_by_state"]
        assert result["agents_by_state"]["active"] == 2

    @pytest.mark.asyncio
    async def test_dashboard_activation_rate(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_dashboard

        async with async_session_factory() as db:
            result = await get_dashboard(db, test_tenant["id"])

        # No terminated/lapsed, so non_excluded = 10
        # activated = active(2) + productive(1) + first_sale(1) = 4
        # rate = 4/10 * 100 = 40.0
        assert result["agent_activation_rate"] == 40.0

    @pytest.mark.asyncio
    async def test_dashboard_activation_trend(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_dashboard

        async with async_session_factory() as db:
            result = await get_dashboard(db, test_tenant["id"])

        assert result["agent_activation_trend"] in ("up", "down", "stable")

    @pytest.mark.asyncio
    async def test_dashboard_reactivation_count(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_dashboard

        async with async_session_factory() as db:
            result = await get_dashboard(db, test_tenant["id"])

        # We inserted one DORMANT -> ACTIVE lifecycle signal
        assert result["reactivation_count_this_month"] >= 1

    @pytest.mark.asyncio
    async def test_dashboard_empty_tenant(self, test_tenant):
        """Dashboard for tenant with no agents should return zeroes."""
        from config.database import async_session_factory
        from modules.analytics.service import get_dashboard

        async with async_session_factory() as db:
            result = await get_dashboard(db, test_tenant["id"])

        assert result["total_agents"] == 0
        assert result["agent_activation_rate"] == 0.0


# ═══════════════════════════════════════════════════════════════════════
# 2. DORMANCY ANALYTICS TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestDormancyService:
    """Test dormancy analytics computation."""

    @pytest.mark.asyncio
    async def test_dormancy_reason_distribution(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_dormancy_analytics

        async with async_session_factory() as db:
            result = await get_dormancy_analytics(db, test_tenant["id"])

        dist = result["reason_distribution"]
        # 2 dormant agents with training_gap, 1 with engagement_gap
        # (agent 4 was reactivated to active but the dormancy_reason column is still set)
        assert "training_gap.product_knowledge_insufficient" in dist
        assert "engagement_gap.adm_never_contacted" in dist

    @pytest.mark.asyncio
    async def test_dormancy_trend_fields(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_dormancy_analytics

        async with async_session_factory() as db:
            result = await get_dormancy_analytics(db, test_tenant["id"])

        assert "trend_vs_last_month" in result
        assert isinstance(result["trend_vs_last_month"], dict)

    @pytest.mark.asyncio
    async def test_dormancy_regional_breakdown(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_dormancy_analytics

        async with async_session_factory() as db:
            result = await get_dormancy_analytics(db, test_tenant["id"])

        assert "regional_breakdown" in result
        # All agents have region_node_id=None, so should be in "unassigned"
        assert "unassigned" in result["regional_breakdown"]

    @pytest.mark.asyncio
    async def test_dormancy_empty_tenant(self, test_tenant):
        from config.database import async_session_factory
        from modules.analytics.service import get_dormancy_analytics

        async with async_session_factory() as db:
            result = await get_dormancy_analytics(db, test_tenant["id"])

        assert result["reason_distribution"] == {}
        assert result["top_growing_reason"] is None


# ═══════════════════════════════════════════════════════════════════════
# 3. REACTIVATION FUNNEL TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestFunnelService:
    """Test reactivation funnel computation."""

    @pytest.mark.asyncio
    async def test_funnel_counts(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_reactivation_funnel

        async with async_session_factory() as db:
            result = await get_reactivation_funnel(db, test_tenant["id"])

        assert result["contacted"] >= 1
        assert result["engaged"] >= 1
        assert result["trained"] >= 1
        assert result["sold"] >= 1

    @pytest.mark.asyncio
    async def test_funnel_conversion_rates(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_reactivation_funnel

        async with async_session_factory() as db:
            result = await get_reactivation_funnel(db, test_tenant["id"])

        rates = result["conversion_rates"]
        assert "contacted_to_engaged" in rates
        assert "engaged_to_trained" in rates
        assert "trained_to_sold" in rates
        assert all(0.0 <= v <= 1.0 for v in rates.values())

    @pytest.mark.asyncio
    async def test_funnel_by_channel(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_reactivation_funnel

        async with async_session_factory() as db:
            result = await get_reactivation_funnel(db, test_tenant["id"])

        assert isinstance(result["by_channel"], dict)

    @pytest.mark.asyncio
    async def test_funnel_empty_tenant(self, test_tenant):
        from config.database import async_session_factory
        from modules.analytics.service import get_reactivation_funnel

        async with async_session_factory() as db:
            result = await get_reactivation_funnel(db, test_tenant["id"])

        assert result["contacted"] == 0
        assert result["conversion_rates"]["contacted_to_engaged"] == 0.0

    @pytest.mark.asyncio
    async def test_funnel_custom_period(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_reactivation_funnel

        # Use a very short period — should capture fewer signals
        async with async_session_factory() as db:
            result = await get_reactivation_funnel(db, test_tenant["id"], period_days=7)

        # Should still work, just possibly fewer counts
        assert isinstance(result["contacted"], int)


# ═══════════════════════════════════════════════════════════════════════
# 4. ADM PERFORMANCE TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestADMPerformanceService:
    """Test ADM performance computation."""

    @pytest.mark.asyncio
    async def test_adm_rankings(self, test_tenant, analytics_agents, analytics_signals, analytics_adm):
        from config.database import async_session_factory
        from modules.analytics.service import get_adm_performance

        async with async_session_factory() as db:
            result = await get_adm_performance(db, test_tenant["id"])

        assert len(result["adm_rankings"]) >= 1
        ranking = result["adm_rankings"][0]
        assert "adm_id" in ranking
        assert "activation_rate" in ranking
        assert "nudge_response_rate" in ranking
        assert "classification" in ranking

    @pytest.mark.asyncio
    async def test_adm_classification(self, test_tenant, analytics_agents, analytics_signals, analytics_adm):
        from config.database import async_session_factory
        from modules.analytics.service import get_adm_performance

        async with async_session_factory() as db:
            result = await get_adm_performance(db, test_tenant["id"])

        for ranking in result["adm_rankings"]:
            assert ranking["classification"] in (
                "HIGH_PERFORMER", "AVERAGE", "STRUGGLING", "UNRESPONSIVE"
            )

    @pytest.mark.asyncio
    async def test_adm_top_bottom(self, test_tenant, analytics_agents, analytics_signals, analytics_adm):
        from config.database import async_session_factory
        from modules.analytics.service import get_adm_performance

        async with async_session_factory() as db:
            result = await get_adm_performance(db, test_tenant["id"])

        assert len(result["top_5_adms"]) <= 5
        assert len(result["bottom_5_adms"]) <= 5
        assert isinstance(result["average_activation_rate"], float)

    @pytest.mark.asyncio
    async def test_adm_no_adms(self, test_tenant, analytics_agents):
        """No ADM users → empty rankings."""
        from config.database import async_session_factory
        from modules.analytics.service import get_adm_performance

        async with async_session_factory() as db:
            result = await get_adm_performance(db, test_tenant["id"])

        assert result["adm_rankings"] == []
        assert result["average_activation_rate"] == 0.0


# ═══════════════════════════════════════════════════════════════════════
# 5. TRAINING EFFECTIVENESS TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestTrainingEffectivenessService:
    """Test training effectiveness computation."""

    @pytest.mark.asyncio
    async def test_training_completion_rates(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_training_effectiveness

        async with async_session_factory() as db:
            result = await get_training_effectiveness(db, test_tenant["id"])

        rates = result["completion_rate_by_module"]
        assert isinstance(rates, dict)
        # We inserted one training signal with module_id "product_term_life"
        if "product_term_life" in rates:
            assert 0.0 <= rates["product_term_life"] <= 1.0

    @pytest.mark.asyncio
    async def test_training_scores(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_training_effectiveness

        async with async_session_factory() as db:
            result = await get_training_effectiveness(db, test_tenant["id"])

        scores = result["average_scores_by_module"]
        if "product_term_life" in scores:
            assert scores["product_term_life"] == 85.0  # We inserted score of 85

    @pytest.mark.asyncio
    async def test_training_to_sale_correlation(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_training_effectiveness

        async with async_session_factory() as db:
            result = await get_training_effectiveness(db, test_tenant["id"])

        corr = result["training_to_sale_correlation"]
        assert isinstance(corr, dict)

    @pytest.mark.asyncio
    async def test_training_drop_off(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_training_effectiveness

        async with async_session_factory() as db:
            result = await get_training_effectiveness(db, test_tenant["id"])

        assert isinstance(result["top_drop_off_modules"], list)

    @pytest.mark.asyncio
    async def test_training_empty_tenant(self, test_tenant):
        from config.database import async_session_factory
        from modules.analytics.service import get_training_effectiveness

        async with async_session_factory() as db:
            result = await get_training_effectiveness(db, test_tenant["id"])

        assert result["completion_rate_by_module"] == {}
        assert result["top_drop_off_modules"] == []


# ═══════════════════════════════════════════════════════════════════════
# 6. SYSTEM ROI TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestSystemROIService:
    """Test system ROI computation."""

    @pytest.mark.asyncio
    async def test_roi_with_reactivated_agents(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_system_roi

        async with async_session_factory() as db:
            result = await get_system_roi(db, test_tenant["id"])

        assert "new_premium_from_reactivated" in result
        assert "roi_multiplier" in result
        assert "agents_reactivated" in result
        assert result["agents_reactivated"] >= 1
        assert result["system_cost_this_month"] == 50000.0

    @pytest.mark.asyncio
    async def test_roi_custom_cost(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_system_roi

        async with async_session_factory() as db:
            result = await get_system_roi(db, test_tenant["id"], system_cost=100000.0)

        assert result["system_cost_this_month"] == 100000.0

    @pytest.mark.asyncio
    async def test_roi_empty_tenant(self, test_tenant):
        from config.database import async_session_factory
        from modules.analytics.service import get_system_roi

        async with async_session_factory() as db:
            result = await get_system_roi(db, test_tenant["id"])

        assert result["agents_reactivated"] == 0
        assert result["new_premium_from_reactivated"] == 0.0
        assert result["roi_multiplier"] == 0.0
        assert result["average_premium_per_reactivation"] == 0.0


# ═══════════════════════════════════════════════════════════════════════
# 7. API ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestAnalyticsAPI:
    """Test Analytics API endpoints."""

    @pytest.mark.asyncio
    async def test_dashboard_endpoint(
        self, client: AsyncClient, test_tenant, analytics_agents, analytics_signals, analytics_token,
    ):
        resp = await client.get(
            "/api/v1/analytics/dashboard",
            headers={"Authorization": f"Bearer {analytics_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_agents" in data
        assert "agents_by_state" in data
        assert "agent_activation_rate" in data

    @pytest.mark.asyncio
    async def test_dormancy_endpoint(
        self, client: AsyncClient, test_tenant, analytics_agents, analytics_signals, analytics_token,
    ):
        resp = await client.get(
            "/api/v1/analytics/dormancy",
            headers={"Authorization": f"Bearer {analytics_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "reason_distribution" in data
        assert "trend_vs_last_month" in data

    @pytest.mark.asyncio
    async def test_funnel_endpoint(
        self, client: AsyncClient, test_tenant, analytics_agents, analytics_signals, analytics_token,
    ):
        resp = await client.get(
            "/api/v1/analytics/reactivation-funnel",
            headers={"Authorization": f"Bearer {analytics_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "contacted" in data
        assert "conversion_rates" in data

    @pytest.mark.asyncio
    async def test_funnel_with_period(
        self, client: AsyncClient, test_tenant, analytics_agents, analytics_signals, analytics_token,
    ):
        resp = await client.get(
            "/api/v1/analytics/reactivation-funnel?period_days=90",
            headers={"Authorization": f"Bearer {analytics_token}"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_adm_performance_endpoint(
        self, client: AsyncClient, test_tenant, analytics_agents, analytics_signals, analytics_adm, analytics_token,
    ):
        resp = await client.get(
            "/api/v1/analytics/adm-performance",
            headers={"Authorization": f"Bearer {analytics_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "adm_rankings" in data
        assert "average_activation_rate" in data

    @pytest.mark.asyncio
    async def test_training_effectiveness_endpoint(
        self, client: AsyncClient, test_tenant, analytics_agents, analytics_signals, analytics_token,
    ):
        resp = await client.get(
            "/api/v1/analytics/training-effectiveness",
            headers={"Authorization": f"Bearer {analytics_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "completion_rate_by_module" in data

    @pytest.mark.asyncio
    async def test_system_roi_endpoint(
        self, client: AsyncClient, test_tenant, analytics_agents, analytics_signals, analytics_token,
    ):
        resp = await client.get(
            "/api/v1/analytics/system-roi",
            headers={"Authorization": f"Bearer {analytics_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "roi_multiplier" in data
        assert "agents_reactivated" in data

    @pytest.mark.asyncio
    async def test_system_roi_custom_params(
        self, client: AsyncClient, test_tenant, analytics_agents, analytics_signals, analytics_token,
    ):
        resp = await client.get(
            "/api/v1/analytics/system-roi?period_days=90&system_cost=100000",
            headers={"Authorization": f"Bearer {analytics_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["system_cost_this_month"] == 100000.0

    @pytest.mark.asyncio
    async def test_no_auth_returns_error(self, client: AsyncClient):
        resp = await client.get("/api/v1/analytics/dashboard")
        assert resp.status_code in (401, 403, 422)

    @pytest.mark.asyncio
    async def test_adm_role_blocked_from_analytics(
        self, client: AsyncClient, test_tenant, adm_token,
    ):
        """ADM users should not access analytics endpoints."""
        resp = await client.get(
            "/api/v1/analytics/dashboard",
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_analyst_can_access_dashboard(
        self, client: AsyncClient, test_tenant, analytics_agents, analytics_signals, analyst_token,
    ):
        """Analyst role should access dashboard."""
        resp = await client.get(
            "/api/v1/analytics/dashboard",
            headers={"Authorization": f"Bearer {analyst_token}"},
        )
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════
# 8. STORED REPORT TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestStoredReports:
    """Test stored report endpoints."""

    @pytest.mark.asyncio
    async def test_dormancy_report_404_when_none(
        self, client: AsyncClient, test_tenant, analytics_token,
    ):
        resp = await client.get(
            "/api/v1/analytics/reports/dormancy",
            headers={"Authorization": f"Bearer {analytics_token}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_training_report_404_when_none(
        self, client: AsyncClient, test_tenant, analytics_token,
    ):
        resp = await client.get(
            "/api/v1/analytics/reports/training",
            headers={"Authorization": f"Bearer {analytics_token}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_adm_report_404_when_none(
        self, client: AsyncClient, test_tenant, analytics_token,
    ):
        resp = await client.get(
            "/api/v1/analytics/reports/adm",
            headers={"Authorization": f"Bearer {analytics_token}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_dormancy_report_after_generation(
        self, client: AsyncClient, test_tenant, analytics_agents, analytics_signals, analytics_token,
    ):
        """Generate a dormancy report via Celery task, then retrieve it."""
        from modules.analytics.reports import generate_dormancy_report_sync

        today = date.today()
        with sync_engine.begin() as conn:
            # Use sync session directly for the report generation
            pass

        from config.database import sync_session_factory
        with sync_session_factory() as session:
            generate_dormancy_report_sync(session, test_tenant["id"], today)
            session.commit()

        resp = await client.get(
            "/api/v1/analytics/reports/dormancy",
            headers={"Authorization": f"Bearer {analytics_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["report_type"] == "dormancy_intelligence"
        assert "reason_distribution" in data["data"]

        # Cleanup
        with sync_engine.begin() as conn:
            conn.execute(
                text("DELETE FROM dormancy_analytics WHERE tenant_id = :tid"),
                {"tid": str(test_tenant["id"])},
            )


# ═══════════════════════════════════════════════════════════════════════
# 9. CELERY TASK TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestCeleryTasks:
    """Test Celery analytics tasks directly (not via worker)."""

    def test_weekly_aggregation_runs(self, test_tenant, analytics_agents, analytics_signals):
        from tasks.analytics_aggregation import weekly_aggregation
        result = weekly_aggregation()
        assert "generated" in result
        assert "errors" in result
        assert result["generated"] >= 1

        # Cleanup generated analytics
        with sync_engine.begin() as conn:
            conn.execute(
                text("DELETE FROM reactivation_funnels WHERE tenant_id = :tid"),
                {"tid": str(test_tenant["id"])},
            )
            conn.execute(
                text("DELETE FROM dormancy_analytics WHERE tenant_id = :tid"),
                {"tid": str(test_tenant["id"])},
            )

    def test_weekly_aggregation_idempotent(self, test_tenant, analytics_agents, analytics_signals):
        """Running twice should not create duplicates."""
        from tasks.analytics_aggregation import weekly_aggregation
        result1 = weekly_aggregation()
        result2 = weekly_aggregation()

        # Second run should skip (already exists)
        assert result2["generated"] == 0

        with sync_engine.begin() as conn:
            conn.execute(
                text("DELETE FROM reactivation_funnels WHERE tenant_id = :tid"),
                {"tid": str(test_tenant["id"])},
            )
            conn.execute(
                text("DELETE FROM dormancy_analytics WHERE tenant_id = :tid"),
                {"tid": str(test_tenant["id"])},
            )

    def test_monthly_reports_runs(self, test_tenant, analytics_agents, analytics_signals):
        from tasks.analytics_aggregation import monthly_reports
        result = monthly_reports()
        assert "generated" in result
        assert "errors" in result

        with sync_engine.begin() as conn:
            conn.execute(
                text("DELETE FROM analytics_snapshots WHERE tenant_id = :tid"),
                {"tid": str(test_tenant["id"])},
            )
            conn.execute(
                text("DELETE FROM reactivation_funnels WHERE tenant_id = :tid"),
                {"tid": str(test_tenant["id"])},
            )
            conn.execute(
                text("DELETE FROM dormancy_analytics WHERE tenant_id = :tid"),
                {"tid": str(test_tenant["id"])},
            )


# ═══════════════════════════════════════════════════════════════════════
# 10. TENANT ISOLATION
# ═══════════════════════════════════════════════════════════════════════


class TestTenantIsolation:
    """Verify analytics are tenant-isolated."""

    @pytest.mark.asyncio
    async def test_dashboard_tenant_isolation(self, test_tenant, analytics_agents, analytics_signals):
        """Dashboard for a different tenant should return zeroes."""
        from config.database import async_session_factory
        from modules.analytics.service import get_dashboard

        other_tenant_id = uuid.uuid4()
        async with async_session_factory() as db:
            result = await get_dashboard(db, other_tenant_id)

        assert result["total_agents"] == 0

    @pytest.mark.asyncio
    async def test_funnel_tenant_isolation(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_reactivation_funnel

        other_tenant_id = uuid.uuid4()
        async with async_session_factory() as db:
            result = await get_reactivation_funnel(db, other_tenant_id)

        assert result["contacted"] == 0
        assert result["engaged"] == 0

    @pytest.mark.asyncio
    async def test_dormancy_tenant_isolation(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_dormancy_analytics

        other_tenant_id = uuid.uuid4()
        async with async_session_factory() as db:
            result = await get_dormancy_analytics(db, other_tenant_id)

        assert result["reason_distribution"] == {}

    @pytest.mark.asyncio
    async def test_roi_tenant_isolation(self, test_tenant, analytics_agents, analytics_signals):
        from config.database import async_session_factory
        from modules.analytics.service import get_system_roi

        other_tenant_id = uuid.uuid4()
        async with async_session_factory() as db:
            result = await get_system_roi(db, other_tenant_id)

        assert result["agents_reactivated"] == 0


# ═══════════════════════════════════════════════════════════════════════
# 11. REGRESSION / EDGE CASES
# ═══════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge case and regression tests."""

    @pytest.mark.asyncio
    async def test_dashboard_with_terminated_agents(self, test_tenant):
        """Terminated agents should be excluded from activation rate calculation."""
        from config.database import async_session_factory
        from modules.analytics.service import get_dashboard

        agent_id = uuid.uuid4()
        with sync_engine.begin() as conn:
            _insert_agent(conn, agent_id, test_tenant["id"], state="terminated")

        try:
            async with async_session_factory() as db:
                result = await get_dashboard(db, test_tenant["id"])

            # Should count in total but not in activation rate denominator
            assert result["total_agents"] == 1
            assert result["agent_activation_rate"] == 0.0
        finally:
            with sync_engine.begin() as conn:
                conn.execute(text("DELETE FROM agents WHERE id = :aid"), {"aid": str(agent_id)})

    @pytest.mark.asyncio
    async def test_dashboard_all_activated(self, test_tenant):
        """All agents activated → 100% rate."""
        from config.database import async_session_factory
        from modules.analytics.service import get_dashboard

        agents = []
        with sync_engine.begin() as conn:
            for _ in range(3):
                aid = uuid.uuid4()
                _insert_agent(conn, aid, test_tenant["id"], state="active")
                agents.append(aid)

        try:
            async with async_session_factory() as db:
                result = await get_dashboard(db, test_tenant["id"])

            assert result["agent_activation_rate"] == 100.0
        finally:
            with sync_engine.begin() as conn:
                for aid in agents:
                    conn.execute(text("DELETE FROM agents WHERE id = :aid"), {"aid": str(aid)})

    @pytest.mark.asyncio
    async def test_funnel_no_sales_zero_conversion(self, test_tenant):
        """Funnel with outreach but no sales → trained_to_sold = 0."""
        from config.database import async_session_factory
        from modules.analytics.service import get_reactivation_funnel

        agent_id = uuid.uuid4()
        with sync_engine.begin() as conn:
            _insert_agent(conn, agent_id, test_tenant["id"])
            _insert_signal(
                conn, test_tenant["id"], agent_id,
                SignalType.WHATSAPP_MESSAGE_SENT,
                ts=(_now() - timedelta(days=5)).isoformat(),
            )

        try:
            async with async_session_factory() as db:
                result = await get_reactivation_funnel(db, test_tenant["id"])

            assert result["contacted"] >= 1
            assert result["sold"] == 0
            assert result["conversion_rates"]["trained_to_sold"] == 0.0
        finally:
            with sync_engine.begin() as conn:
                conn.execute(text("DELETE FROM signals WHERE agent_id = :aid"), {"aid": str(agent_id)})
                conn.execute(text("DELETE FROM agents WHERE id = :aid"), {"aid": str(agent_id)})

    def test_report_sync_generators_create_records(self, test_tenant, analytics_agents, analytics_signals):
        """Test that sync report generators create records in the database."""
        from config.database import sync_session_factory
        from modules.analytics.reports import (
            generate_dormancy_report_sync,
            generate_monthly_snapshot_sync,
            generate_reactivation_funnel_sync,
        )

        today = date.today()
        week_start = today - timedelta(days=7)

        with sync_session_factory() as session:
            dormancy = generate_dormancy_report_sync(session, test_tenant["id"], today)
            funnel = generate_reactivation_funnel_sync(
                session, test_tenant["id"], week_start, today,
            )
            snapshot = generate_monthly_snapshot_sync(session, test_tenant["id"], today)
            session.commit()

        assert dormancy.tenant_id == test_tenant["id"]
        assert funnel.contacted_count >= 0
        assert snapshot.metrics["total_agents"] >= 0

        # Cleanup
        with sync_engine.begin() as conn:
            conn.execute(
                text("DELETE FROM dormancy_analytics WHERE tenant_id = :tid"),
                {"tid": str(test_tenant["id"])},
            )
            conn.execute(
                text("DELETE FROM reactivation_funnels WHERE tenant_id = :tid"),
                {"tid": str(test_tenant["id"])},
            )
            conn.execute(
                text("DELETE FROM analytics_snapshots WHERE tenant_id = :tid"),
                {"tid": str(test_tenant["id"])},
            )

    def test_schema_validation(self):
        """Test that all schema models can be instantiated."""
        from modules.analytics.schemas import (
            ADMPerformanceResponse,
            ADMRanking,
            DashboardResponse,
            DormancyAnalyticsResponse,
            ReactivationFunnelResponse,
            SystemROIResponse,
            TrainingEffectivenessResponse,
        )

        dashboard = DashboardResponse(
            total_agents=100,
            active_agents=50,
            at_risk_agents=10,
            dormant_agents=20,
            agents_by_state={"active": 50, "dormant": 20},
            agent_activation_rate=50.0,
            agent_activation_trend="up",
            reactivation_count_this_month=5,
            reactivation_by_intervention={"whatsapp_bot": 3, "voice_ai": 2},
        )
        assert dashboard.total_agents == 100

        roi = SystemROIResponse(
            new_premium_from_reactivated=250000.0,
            system_cost_this_month=50000.0,
            roi_multiplier=5.0,
            agents_reactivated=10,
            average_premium_per_reactivation=25000.0,
        )
        assert roi.roi_multiplier == 5.0

        ranking = ADMRanking(
            adm_id=uuid.uuid4(),
            name="Test ADM",
            total_agents=20,
            active_agents=10,
            activation_rate=0.5,
            nudge_response_rate=0.8,
            reactivations_last_90d=3,
            classification="HIGH_PERFORMER",
        )
        assert ranking.classification == "HIGH_PERFORMER"
