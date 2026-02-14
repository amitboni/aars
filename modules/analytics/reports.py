"""modules/analytics/reports.py — Periodic report generators.

Per spec section 3.7.2: dormancy intelligence, training effectiveness,
ADM performance reports. Generated monthly and stored in AnalyticsSnapshot.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from core.enums import AgentLifecycleState, SignalType, UserRole
from modules.agent.models import Agent
from modules.analytics.models import AnalyticsSnapshot, DormancyAnalytics, ReactivationFunnel
from modules.signal.models import Signal
from modules.user.models import User

logger = logging.getLogger(__name__)

# States considered "activated"
_ACTIVATED_STATES = {
    AgentLifecycleState.FIRST_SALE,
    AgentLifecycleState.ACTIVE,
    AgentLifecycleState.PRODUCTIVE,
}

_EXCLUDED_STATES = {
    AgentLifecycleState.TERMINATED,
    AgentLifecycleState.LAPSED,
}

_OUTREACH_SIGNALS = {
    SignalType.VOICE_CALL_INITIATED,
    SignalType.WHATSAPP_MESSAGE_SENT,
    SignalType.ADM_AGENT_CALL_LOGGED,
    SignalType.ADM_AGENT_VISIT_LOGGED,
}

_ENGAGEMENT_SIGNALS = {
    SignalType.VOICE_CALL_OUTCOME,
    SignalType.WHATSAPP_AGENT_REPLIED,
    SignalType.ADM_AGENT_CALL_LOGGED,
    SignalType.ADM_AGENT_VISIT_LOGGED,
}

_TRAINING_SIGNALS = {
    SignalType.WHATSAPP_TRAINING_INTERACTION,
    SignalType.TRAINING_COMPLETED_EXTERNAL,
}


def generate_dormancy_report_sync(
    session: Session,
    tenant_id: uuid.UUID,
    snapshot_date: date,
) -> DormancyAnalytics:
    """Generate dormancy intelligence report (sync, for Celery).

    Computes reason distribution, trend vs previous period, and regional breakdown.
    Stores result in dormancy_analytics table.
    """
    now = datetime.combine(snapshot_date, datetime.min.time(), tzinfo=timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    sixty_days_ago = now - timedelta(days=60)

    # Current dormant agents grouped by reason
    result = session.execute(
        select(Agent).where(
            Agent.tenant_id == tenant_id,
            Agent.deleted_at.is_(None),
            Agent.lifecycle_state == AgentLifecycleState.DORMANT,
        )
    )
    dormant_agents = list(result.scalars().all())

    reason_dist: dict[str, int] = {}
    regional: dict[str, dict[str, int]] = {}
    for agent in dormant_agents:
        reason = agent.dormancy_reason or "unknown"
        reason_dist[reason] = reason_dist.get(reason, 0) + 1
        region_key = str(agent.region_node_id) if agent.region_node_id else "unassigned"
        if region_key not in regional:
            regional[region_key] = {}
        regional[region_key][reason] = regional[region_key].get(reason, 0) + 1

    # Previous month dormancy signals for trend
    prev_signals = session.execute(
        select(Signal).where(
            Signal.tenant_id == tenant_id,
            Signal.signal_type == SignalType.LIFECYCLE_STATE_CHANGED,
            Signal.timestamp >= sixty_days_ago,
            Signal.timestamp < thirty_days_ago,
        )
    )
    prev_counts: dict[str, int] = {}
    for sig in prev_signals.scalars().all():
        payload = sig.payload or {}
        if payload.get("new_state") == AgentLifecycleState.DORMANT:
            reason = payload.get("dormancy_reason", "unknown")
            prev_counts[reason] = prev_counts.get(reason, 0) + 1

    # Compute trends
    all_reasons = set(reason_dist.keys()) | set(prev_counts.keys())
    trend: dict[str, float] = {}
    for reason in all_reasons:
        current = reason_dist.get(reason, 0)
        previous = prev_counts.get(reason, 0)
        if previous > 0:
            trend[reason] = round((current - previous) / previous * 100, 2)
        elif current > 0:
            trend[reason] = 100.0
        else:
            trend[reason] = 0.0

    record = DormancyAnalytics(
        tenant_id=tenant_id,
        snapshot_date=snapshot_date,
        reason_distribution=reason_dist,
        trend_vs_previous=trend,
        regional_breakdown=regional,
    )
    session.add(record)
    return record


def generate_reactivation_funnel_sync(
    session: Session,
    tenant_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> ReactivationFunnel:
    """Generate reactivation funnel snapshot (sync, for Celery).

    Computes contacted -> engaged -> trained -> sold pipeline for the period.
    Stores result in reactivation_funnels table.
    """
    ps_dt = datetime.combine(period_start, datetime.min.time(), tzinfo=timezone.utc)
    pe_dt = datetime.combine(period_end, datetime.max.time(), tzinfo=timezone.utc)

    # Get all signals in the period
    result = session.execute(
        select(Signal).where(
            Signal.tenant_id == tenant_id,
            Signal.timestamp >= ps_dt,
            Signal.timestamp <= pe_dt,
            Signal.agent_id.isnot(None),
        )
    )
    signals = list(result.scalars().all())

    # Group signals by agent
    agent_signals: dict[uuid.UUID, list] = {}
    for sig in signals:
        if sig.agent_id:
            agent_signals.setdefault(sig.agent_id, []).append(sig)

    contacted_agents: set[uuid.UUID] = set()
    engaged_agents: set[uuid.UUID] = set()
    trained_agents: set[uuid.UUID] = set()
    sold_agents: set[uuid.UUID] = set()

    channel_data: dict[str, dict[str, int]] = {}
    playbook_data: dict[str, dict[str, int]] = {}

    for agent_id, sigs in agent_signals.items():
        has_outreach = False
        has_engagement = False
        has_training = False
        has_sale = False
        channels: set[str] = set()
        playbooks: set[str] = set()

        for sig in sigs:
            channel = sig.channel or sig.source or "unknown"
            meta = sig.metadata_ or {}
            pb = meta.get("playbook_id")
            if pb:
                playbooks.add(str(pb))

            if sig.signal_type in _OUTREACH_SIGNALS:
                has_outreach = True
                channels.add(channel)

            if sig.signal_type in _ENGAGEMENT_SIGNALS:
                payload = sig.payload or {}
                if sig.signal_type == SignalType.VOICE_CALL_OUTCOME:
                    outcome = payload.get("outcome", "")
                    if outcome in ("answered", "completed"):
                        has_engagement = True
                        channels.add(channel)
                else:
                    has_engagement = True
                    channels.add(channel)

            if sig.signal_type in _TRAINING_SIGNALS:
                payload = sig.payload or {}
                if sig.signal_type == SignalType.WHATSAPP_TRAINING_INTERACTION:
                    completion = payload.get("completion_percentage", 0)
                    interaction_type = payload.get("interaction_type", "")
                    if (completion and float(completion) > 50) or interaction_type == "QUIZ_COMPLETED":
                        has_training = True
                elif sig.signal_type == SignalType.TRAINING_COMPLETED_EXTERNAL:
                    has_training = True

            if sig.signal_type == SignalType.POLICY_SOLD:
                has_sale = True

        if has_outreach:
            contacted_agents.add(agent_id)
        if has_engagement:
            engaged_agents.add(agent_id)
        if has_training:
            trained_agents.add(agent_id)
        if has_sale:
            sold_agents.add(agent_id)

        # Per-channel/playbook aggregation
        for ch in channels:
            if ch not in channel_data:
                channel_data[ch] = {"contacted": 0, "engaged": 0, "trained": 0, "sold": 0}
            if has_outreach:
                channel_data[ch]["contacted"] += 1
            if has_engagement:
                channel_data[ch]["engaged"] += 1
            if has_training:
                channel_data[ch]["trained"] += 1
            if has_sale:
                channel_data[ch]["sold"] += 1

        for pb in playbooks:
            if pb not in playbook_data:
                playbook_data[pb] = {"contacted": 0, "engaged": 0, "trained": 0, "sold": 0}
            if has_outreach:
                playbook_data[pb]["contacted"] += 1
            if has_engagement:
                playbook_data[pb]["engaged"] += 1
            if has_training:
                playbook_data[pb]["trained"] += 1
            if has_sale:
                playbook_data[pb]["sold"] += 1

    record = ReactivationFunnel(
        tenant_id=tenant_id,
        period_start=period_start,
        period_end=period_end,
        contacted_count=len(contacted_agents),
        engaged_count=len(engaged_agents),
        trained_count=len(trained_agents),
        sold_count=len(sold_agents),
        funnel_by_channel=channel_data,
        funnel_by_playbook=playbook_data,
    )
    session.add(record)
    return record


def generate_monthly_snapshot_sync(
    session: Session,
    tenant_id: uuid.UUID,
    snapshot_date: date,
) -> AnalyticsSnapshot:
    """Generate monthly analytics snapshot (sync, for Celery).

    Computes dashboard metrics, ADM performance, and training effectiveness.
    Stores result in analytics_snapshots table.
    """
    now = datetime.combine(snapshot_date, datetime.min.time(), tzinfo=timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    ninety_days_ago = now - timedelta(days=90)

    # Agent state counts
    result = session.execute(
        select(Agent).where(
            Agent.tenant_id == tenant_id,
            Agent.deleted_at.is_(None),
        )
    )
    agents = list(result.scalars().all())

    state_counts: dict[str, int] = {}
    for agent in agents:
        state_counts[agent.lifecycle_state] = state_counts.get(agent.lifecycle_state, 0) + 1

    total = len(agents)
    non_excluded = sum(c for s, c in state_counts.items() if s not in _EXCLUDED_STATES)
    activated = sum(c for s, c in state_counts.items() if s in _ACTIVATED_STATES)
    activation_rate = (activated / non_excluded * 100) if non_excluded > 0 else 0.0

    # ADM performance summary
    adm_result = session.execute(
        select(User).where(
            User.tenant_id == tenant_id,
            User.deleted_at.is_(None),
            User.is_active.is_(True),
        )
    )
    all_users = list(adm_result.scalars().all())
    adm_users = [u for u in all_users if "adm" in (u.roles or [])]

    adm_summary = []
    for adm in adm_users:
        adm_agents = [a for a in agents if a.assigned_adm_id == adm.id]
        adm_active = sum(1 for a in adm_agents if a.lifecycle_state in _ACTIVATED_STATES)
        adm_non_excluded = sum(1 for a in adm_agents if a.lifecycle_state not in _EXCLUDED_STATES)
        rate = adm_active / adm_non_excluded if adm_non_excluded > 0 else 0.0
        adm_summary.append({
            "adm_id": str(adm.id),
            "name": adm.full_name,
            "total_agents": len(adm_agents),
            "activation_rate": round(rate, 4),
        })

    # Training completion summary
    training_result = session.execute(
        select(Signal).where(
            Signal.tenant_id == tenant_id,
            Signal.signal_type == SignalType.WHATSAPP_TRAINING_INTERACTION,
            Signal.timestamp >= ninety_days_ago,
            Signal.agent_id.isnot(None),
        )
    )
    training_signals = list(training_result.scalars().all())

    module_started: dict[str, set] = {}
    module_completed: dict[str, set] = {}
    for sig in training_signals:
        payload = sig.payload or {}
        module_id = payload.get("module_id", "unknown")
        agent_id = sig.agent_id
        if not agent_id:
            continue
        module_started.setdefault(module_id, set()).add(agent_id)
        interaction_type = payload.get("interaction_type", "")
        completion_pct = payload.get("completion_percentage", 0)
        if interaction_type == "QUIZ_COMPLETED" or (completion_pct and float(completion_pct) >= 80):
            module_completed.setdefault(module_id, set()).add(agent_id)

    training_summary = {}
    for module_id in module_started:
        started = len(module_started[module_id])
        completed = len(module_completed.get(module_id, set()))
        training_summary[module_id] = {
            "started": started,
            "completed": completed,
            "completion_rate": round(completed / started, 4) if started > 0 else 0.0,
        }

    # Reactivation count
    reactivation_result = session.execute(
        select(Signal).where(
            Signal.tenant_id == tenant_id,
            Signal.signal_type == SignalType.LIFECYCLE_STATE_CHANGED,
            Signal.timestamp >= thirty_days_ago,
        )
    )
    reactivation_count = 0
    for sig in reactivation_result.scalars().all():
        payload = sig.payload or {}
        if (
            payload.get("previous_state") == AgentLifecycleState.DORMANT
            and payload.get("new_state") in (
                AgentLifecycleState.ACTIVE,
                AgentLifecycleState.FIRST_SALE,
                AgentLifecycleState.LICENSED,
            )
        ):
            reactivation_count += 1

    metrics = {
        "total_agents": total,
        "agents_by_state": state_counts,
        "activation_rate": round(activation_rate, 2),
        "reactivation_count": reactivation_count,
        "adm_performance": adm_summary,
        "training_effectiveness": training_summary,
    }

    record = AnalyticsSnapshot(
        tenant_id=tenant_id,
        snapshot_date=snapshot_date,
        snapshot_type="MONTHLY",
        metrics=metrics,
    )
    session.add(record)
    return record
