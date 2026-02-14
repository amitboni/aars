"""modules/analytics/service.py — Analytics computation functions.

Per spec section 3.7.1: dashboard, dormancy, reactivation funnel,
ADM performance, training effectiveness, and system ROI.

All functions take tenant_id and optional region_node_id for role-scoped access.
Regional managers see only their regions; tenant admins see all.
"""
from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, and_, case, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import AgentLifecycleState, SignalType
from modules.agent.models import Agent
from modules.signal.models import Signal
from modules.user.models import User

# States considered "activated" for activation rate
_ACTIVATED_STATES = {
    AgentLifecycleState.FIRST_SALE,
    AgentLifecycleState.ACTIVE,
    AgentLifecycleState.PRODUCTIVE,
}

# States excluded from total when computing activation rate
_EXCLUDED_STATES = {
    AgentLifecycleState.TERMINATED,
    AgentLifecycleState.LAPSED,
}

# Signal types that count as "outreach" (contacted)
_OUTREACH_SIGNALS = {
    SignalType.VOICE_CALL_INITIATED,
    SignalType.WHATSAPP_MESSAGE_SENT,
    SignalType.ADM_AGENT_CALL_LOGGED,
    SignalType.ADM_AGENT_VISIT_LOGGED,
}

# Signal types that count as "engaged" (positive response)
_ENGAGEMENT_SIGNALS = {
    SignalType.VOICE_CALL_OUTCOME,
    SignalType.WHATSAPP_AGENT_REPLIED,
    SignalType.ADM_AGENT_CALL_LOGGED,
    SignalType.ADM_AGENT_VISIT_LOGGED,
}

# Signal types that count as "trained"
_TRAINING_SIGNALS = {
    SignalType.WHATSAPP_TRAINING_INTERACTION,
    SignalType.TRAINING_COMPLETED_EXTERNAL,
}


def _base_agent_query(
    tenant_id: uuid.UUID,
    region_node_id: uuid.UUID | None = None,
):
    """Build base agent query with tenant + region + soft-delete filters."""
    q = select(Agent).where(
        Agent.tenant_id == tenant_id,
        Agent.deleted_at.is_(None),
    )
    if region_node_id:
        q = q.where(Agent.region_node_id == region_node_id)
    return q


# ─── Dashboard ───


async def get_dashboard(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    region_node_id: uuid.UUID | None = None,
) -> dict:
    """Compute executive dashboard metrics (spec section 3.7.1).

    Returns dict matching DashboardResponse schema.
    """
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    sixty_days_ago = now - timedelta(days=60)

    # 1. Agent lifecycle state counts
    q = _base_agent_query(tenant_id, region_node_id)
    result = await db.execute(q)
    agents = list(result.scalars().all())

    state_counts: dict[str, int] = Counter()
    for agent in agents:
        state_counts[agent.lifecycle_state] += 1

    total = len(agents)
    non_excluded = sum(
        c for s, c in state_counts.items() if s not in _EXCLUDED_STATES
    )
    activated = sum(
        c for s, c in state_counts.items() if s in _ACTIVATED_STATES
    )
    activation_rate = (activated / non_excluded * 100) if non_excluded > 0 else 0.0

    # 2. Activation trend vs last month
    # Count agents that were active 30-60 days ago
    prev_activated = 0
    for agent in agents:
        if agent.lifecycle_state in _EXCLUDED_STATES:
            continue
        # Check if agent had a lifecycle change to an activated state in prev month
        # For simplicity, compare current rate vs signals
    prev_result = await db.execute(
        select(func.count(distinct(Signal.agent_id))).where(
            Signal.tenant_id == tenant_id,
            Signal.signal_type == SignalType.LIFECYCLE_STATE_CHANGED,
            Signal.timestamp >= sixty_days_ago,
            Signal.timestamp < thirty_days_ago,
        )
    )
    # Get count of agents that entered activated states last month
    prev_reactivations = prev_result.scalar() or 0

    current_result = await db.execute(
        select(func.count(distinct(Signal.agent_id))).where(
            Signal.tenant_id == tenant_id,
            Signal.signal_type == SignalType.LIFECYCLE_STATE_CHANGED,
            Signal.timestamp >= thirty_days_ago,
        )
    )
    current_transitions = current_result.scalar() or 0

    if current_transitions > prev_reactivations:
        trend = "up"
    elif current_transitions < prev_reactivations:
        trend = "down"
    else:
        trend = "stable"

    # 3. Reactivation count (DORMANT -> ACTIVE/FIRST_SALE in last 30 days)
    reactivation_result = await db.execute(
        select(Signal).where(
            Signal.tenant_id == tenant_id,
            Signal.signal_type == SignalType.LIFECYCLE_STATE_CHANGED,
            Signal.timestamp >= thirty_days_ago,
        )
    )
    reactivation_signals = list(reactivation_result.scalars().all())

    reactivation_count = 0
    reactivated_agent_ids: list[uuid.UUID] = []
    for sig in reactivation_signals:
        payload = sig.payload or {}
        prev_state = payload.get("previous_state", "")
        new_state = payload.get("new_state", "")
        if prev_state == AgentLifecycleState.DORMANT and new_state in (
            AgentLifecycleState.ACTIVE,
            AgentLifecycleState.FIRST_SALE,
            AgentLifecycleState.LICENSED,
        ):
            reactivation_count += 1
            if sig.agent_id:
                reactivated_agent_ids.append(sig.agent_id)

    # 4. Reactivation attribution — what intervention preceded each reactivation
    reactivation_by_intervention: dict[str, int] = defaultdict(int)
    for agent_id in reactivated_agent_ids:
        # Find last outreach signal before the reactivation
        last_outreach = await db.execute(
            select(Signal).where(
                Signal.tenant_id == tenant_id,
                Signal.agent_id == agent_id,
                Signal.signal_type.in_([
                    SignalType.VOICE_CALL_OUTCOME,
                    SignalType.WHATSAPP_AGENT_REPLIED,
                    SignalType.ADM_AGENT_CALL_LOGGED,
                    SignalType.ADM_AGENT_VISIT_LOGGED,
                ]),
                Signal.timestamp >= thirty_days_ago,
                Signal.timestamp <= now,
            ).order_by(Signal.timestamp.desc()).limit(1)
        )
        outreach_sig = last_outreach.scalar_one_or_none()
        if outreach_sig:
            channel = outreach_sig.channel or outreach_sig.source or "unknown"
            reactivation_by_intervention[channel] += 1
        else:
            reactivation_by_intervention["unknown"] += 1

    return {
        "total_agents": total,
        "active_agents": state_counts.get(AgentLifecycleState.ACTIVE, 0)
        + state_counts.get(AgentLifecycleState.PRODUCTIVE, 0),
        "at_risk_agents": state_counts.get(AgentLifecycleState.AT_RISK, 0),
        "dormant_agents": state_counts.get(AgentLifecycleState.DORMANT, 0),
        "agents_by_state": dict(state_counts),
        "agent_activation_rate": round(activation_rate, 2),
        "agent_activation_trend": trend,
        "reactivation_count_this_month": reactivation_count,
        "reactivation_by_intervention": dict(reactivation_by_intervention),
    }


# ─── Dormancy Analytics ───


async def get_dormancy_analytics(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    region_node_id: uuid.UUID | None = None,
) -> dict:
    """Compute dormancy reason distribution and trends.

    Returns dict matching DormancyAnalyticsResponse schema.
    """
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # Current dormant agents grouped by reason
    q = _base_agent_query(tenant_id, region_node_id).where(
        Agent.lifecycle_state == AgentLifecycleState.DORMANT,
    )
    result = await db.execute(q)
    dormant_agents = list(result.scalars().all())

    reason_dist: dict[str, int] = Counter()
    regional: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for agent in dormant_agents:
        reason = agent.dormancy_reason or "unknown"
        reason_dist[reason] += 1
        region_key = str(agent.region_node_id) if agent.region_node_id else "unassigned"
        regional[region_key][reason] += 1

    # Previous month: count dormant agents that had dormancy_reason set via signals
    # We look at LIFECYCLE_STATE_CHANGED signals from 30-60 days ago
    sixty_days_ago = now - timedelta(days=60)
    prev_signals = await db.execute(
        select(Signal).where(
            Signal.tenant_id == tenant_id,
            Signal.signal_type == SignalType.LIFECYCLE_STATE_CHANGED,
            Signal.timestamp >= sixty_days_ago,
            Signal.timestamp < thirty_days_ago,
        )
    )
    prev_dormancy_counts: dict[str, int] = Counter()
    for sig in prev_signals.scalars().all():
        payload = sig.payload or {}
        if payload.get("new_state") == AgentLifecycleState.DORMANT:
            # Try to extract reason from payload or default
            reason = payload.get("dormancy_reason", "unknown")
            prev_dormancy_counts[reason] += 1

    # Compute trends
    all_reasons = set(reason_dist.keys()) | set(prev_dormancy_counts.keys())
    trend: dict[str, float] = {}
    for reason in all_reasons:
        current = reason_dist.get(reason, 0)
        previous = prev_dormancy_counts.get(reason, 0)
        if previous > 0:
            trend[reason] = round((current - previous) / previous * 100, 2)
        elif current > 0:
            trend[reason] = 100.0  # New reason not seen before
        else:
            trend[reason] = 0.0

    # Find top growing and shrinking
    top_growing = None
    top_shrinking = None
    if trend:
        sorted_reasons = sorted(trend.items(), key=lambda x: x[1], reverse=True)
        for reason, change in sorted_reasons:
            if change > 0 and top_growing is None:
                top_growing = reason
            if change < 0 and top_shrinking is None:
                top_shrinking = reason
            if top_growing and top_shrinking:
                break

    return {
        "reason_distribution": dict(reason_dist),
        "top_growing_reason": top_growing,
        "top_shrinking_reason": top_shrinking,
        "trend_vs_last_month": trend,
        "regional_breakdown": {k: dict(v) for k, v in regional.items()},
    }


# ─── Reactivation Funnel ───


async def get_reactivation_funnel(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    period_days: int = 30,
) -> dict:
    """Compute reactivation funnel: contacted -> engaged -> trained -> sold.

    Returns dict matching ReactivationFunnelResponse schema.
    """
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=period_days)

    # Get all signals in the period
    result = await db.execute(
        select(Signal).where(
            Signal.tenant_id == tenant_id,
            Signal.timestamp >= period_start,
            Signal.agent_id.isnot(None),
        )
    )
    signals = list(result.scalars().all())

    # Group signals by agent
    agent_signals: dict[uuid.UUID, list[Signal]] = defaultdict(list)
    for sig in signals:
        if sig.agent_id:
            agent_signals[sig.agent_id].append(sig)

    # Compute funnel per agent
    contacted_agents: set[uuid.UUID] = set()
    engaged_agents: set[uuid.UUID] = set()
    trained_agents: set[uuid.UUID] = set()
    sold_agents: set[uuid.UUID] = set()

    # Per-channel tracking
    channel_contacted: dict[str, set[uuid.UUID]] = defaultdict(set)
    channel_engaged: dict[str, set[uuid.UUID]] = defaultdict(set)
    channel_trained: dict[str, set[uuid.UUID]] = defaultdict(set)
    channel_sold: dict[str, set[uuid.UUID]] = defaultdict(set)

    # Per-playbook tracking
    playbook_contacted: dict[str, set[uuid.UUID]] = defaultdict(set)
    playbook_engaged: dict[str, set[uuid.UUID]] = defaultdict(set)
    playbook_trained: dict[str, set[uuid.UUID]] = defaultdict(set)
    playbook_sold: dict[str, set[uuid.UUID]] = defaultdict(set)

    for agent_id, sigs in agent_signals.items():
        has_outreach = False
        has_engagement = False
        has_training = False
        has_sale = False
        channels: set[str] = set()
        playbooks: set[str] = set()

        for sig in sigs:
            channel = sig.channel or sig.source or "unknown"

            # Track playbook from metadata
            meta = sig.metadata_ or {}
            pb = meta.get("playbook_id")
            if pb:
                playbooks.add(str(pb))

            if sig.signal_type in _OUTREACH_SIGNALS:
                has_outreach = True
                channels.add(channel)

            if sig.signal_type in _ENGAGEMENT_SIGNALS:
                payload = sig.payload or {}
                outcome = payload.get("outcome", "")
                if sig.signal_type == SignalType.VOICE_CALL_OUTCOME:
                    if outcome in ("answered", "completed"):
                        has_engagement = True
                        channels.add(channel)
                elif sig.signal_type == SignalType.WHATSAPP_AGENT_REPLIED:
                    has_engagement = True
                    channels.add(channel)
                elif sig.signal_type in (
                    SignalType.ADM_AGENT_CALL_LOGGED,
                    SignalType.ADM_AGENT_VISIT_LOGGED,
                ):
                    has_engagement = True
                    channels.add(channel)

            if sig.signal_type in _TRAINING_SIGNALS:
                payload = sig.payload or {}
                if sig.signal_type == SignalType.WHATSAPP_TRAINING_INTERACTION:
                    completion = payload.get("completion_percentage", 0)
                    interaction_type = payload.get("interaction_type", "")
                    if completion and float(completion) > 50 or interaction_type == "QUIZ_COMPLETED":
                        has_training = True
                elif sig.signal_type == SignalType.TRAINING_COMPLETED_EXTERNAL:
                    has_training = True

            if sig.signal_type == SignalType.POLICY_SOLD:
                has_sale = True

        if has_outreach:
            contacted_agents.add(agent_id)
            for ch in channels:
                channel_contacted[ch].add(agent_id)
            for pb in playbooks:
                playbook_contacted[pb].add(agent_id)
        if has_engagement:
            engaged_agents.add(agent_id)
            for ch in channels:
                channel_engaged[ch].add(agent_id)
            for pb in playbooks:
                playbook_engaged[pb].add(agent_id)
        if has_training:
            trained_agents.add(agent_id)
            for ch in channels:
                channel_trained[ch].add(agent_id)
            for pb in playbooks:
                playbook_trained[pb].add(agent_id)
        if has_sale:
            sold_agents.add(agent_id)
            for ch in channels:
                channel_sold[ch].add(agent_id)
            for pb in playbooks:
                playbook_sold[pb].add(agent_id)

    contacted = len(contacted_agents)
    engaged = len(engaged_agents)
    trained = len(trained_agents)
    sold = len(sold_agents)

    conversion_rates = {
        "contacted_to_engaged": round(engaged / contacted, 4) if contacted > 0 else 0.0,
        "engaged_to_trained": round(trained / engaged, 4) if engaged > 0 else 0.0,
        "trained_to_sold": round(sold / trained, 4) if trained > 0 else 0.0,
    }

    # Build per-channel breakdown
    all_channels = set(channel_contacted.keys()) | set(channel_engaged.keys())
    by_channel = {}
    for ch in all_channels:
        by_channel[ch] = {
            "contacted": len(channel_contacted.get(ch, set())),
            "engaged": len(channel_engaged.get(ch, set())),
            "trained": len(channel_trained.get(ch, set())),
            "sold": len(channel_sold.get(ch, set())),
        }

    # Build per-playbook breakdown
    all_playbooks = set(playbook_contacted.keys()) | set(playbook_engaged.keys())
    by_playbook = {}
    for pb in all_playbooks:
        by_playbook[pb] = {
            "contacted": len(playbook_contacted.get(pb, set())),
            "engaged": len(playbook_engaged.get(pb, set())),
            "trained": len(playbook_trained.get(pb, set())),
            "sold": len(playbook_sold.get(pb, set())),
        }

    return {
        "contacted": contacted,
        "engaged": engaged,
        "trained": trained,
        "sold": sold,
        "conversion_rates": conversion_rates,
        "by_channel": by_channel,
        "by_playbook": by_playbook,
    }


# ─── ADM Performance ───


async def get_adm_performance(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> dict:
    """Compute ADM performance rankings (spec section 3.7.2).

    Returns dict matching ADMPerformanceResponse schema.
    """
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    ninety_days_ago = now - timedelta(days=90)

    # Get all ADM users
    adm_result = await db.execute(
        select(User).where(
            User.tenant_id == tenant_id,
            User.deleted_at.is_(None),
            User.is_active.is_(True),
        )
    )
    all_users = list(adm_result.scalars().all())
    adm_users = [u for u in all_users if "adm" in (u.roles or [])]

    if not adm_users:
        return {
            "adm_rankings": [],
            "top_5_adms": [],
            "bottom_5_adms": [],
            "average_activation_rate": 0.0,
        }

    # Get all non-deleted agents
    agents_result = await db.execute(
        select(Agent).where(
            Agent.tenant_id == tenant_id,
            Agent.deleted_at.is_(None),
        )
    )
    all_agents = list(agents_result.scalars().all())

    # Group agents by ADM
    agents_by_adm: dict[uuid.UUID, list[Agent]] = defaultdict(list)
    for agent in all_agents:
        if agent.assigned_adm_id:
            agents_by_adm[agent.assigned_adm_id].append(agent)

    # Get nudge signals for all ADMs in last 30 days
    nudge_received_result = await db.execute(
        select(Signal.adm_id, func.count(Signal.id)).where(
            Signal.tenant_id == tenant_id,
            Signal.signal_type == SignalType.ADM_NUDGE_RECEIVED,
            Signal.timestamp >= thirty_days_ago,
        ).group_by(Signal.adm_id)
    )
    nudges_received: dict[uuid.UUID, int] = {}
    for row in nudge_received_result.all():
        if row[0]:
            nudges_received[row[0]] = row[1]

    nudge_acted_result = await db.execute(
        select(Signal.adm_id, func.count(Signal.id)).where(
            Signal.tenant_id == tenant_id,
            Signal.signal_type == SignalType.ADM_NUDGE_ACTED_ON,
            Signal.timestamp >= thirty_days_ago,
        ).group_by(Signal.adm_id)
    )
    nudges_acted: dict[uuid.UUID, int] = {}
    for row in nudge_acted_result.all():
        if row[0]:
            nudges_acted[row[0]] = row[1]

    # Get reactivation signals in last 90 days
    reactivation_result = await db.execute(
        select(Signal).where(
            Signal.tenant_id == tenant_id,
            Signal.signal_type == SignalType.LIFECYCLE_STATE_CHANGED,
            Signal.timestamp >= ninety_days_ago,
        )
    )
    reactivation_by_adm: dict[uuid.UUID, int] = defaultdict(int)
    for sig in reactivation_result.scalars().all():
        payload = sig.payload or {}
        if (
            payload.get("previous_state") == AgentLifecycleState.DORMANT
            and payload.get("new_state") in (
                AgentLifecycleState.ACTIVE,
                AgentLifecycleState.FIRST_SALE,
                AgentLifecycleState.LICENSED,
            )
            and sig.agent_id
        ):
            # Find ADM for this agent
            for agent in all_agents:
                if agent.id == sig.agent_id and agent.assigned_adm_id:
                    reactivation_by_adm[agent.assigned_adm_id] += 1
                    break

    # Build rankings
    rankings = []
    total_activation_rate = 0.0
    for adm in adm_users:
        adm_agents = agents_by_adm.get(adm.id, [])
        total_agents = len(adm_agents)
        active_agents = sum(
            1 for a in adm_agents
            if a.lifecycle_state in _ACTIVATED_STATES
        )
        non_excluded = sum(
            1 for a in adm_agents
            if a.lifecycle_state not in _EXCLUDED_STATES
        )
        activation_rate = (
            active_agents / non_excluded if non_excluded > 0 else 0.0
        )
        total_activation_rate += activation_rate

        received = nudges_received.get(adm.id, 0)
        acted = nudges_acted.get(adm.id, 0)
        nudge_rate = acted / received if received > 0 else 0.0

        reactivations = reactivation_by_adm.get(adm.id, 0)

        # Classification (spec section 2.9)
        if nudge_rate < 0.2 and received > 0:
            classification = "UNRESPONSIVE"
        elif activation_rate > 0.10 and nudge_rate > 0.7:
            classification = "HIGH_PERFORMER"
        elif activation_rate >= 0.03:
            classification = "AVERAGE"
        else:
            classification = "STRUGGLING"

        rankings.append({
            "adm_id": adm.id,
            "name": adm.full_name,
            "total_agents": total_agents,
            "active_agents": active_agents,
            "activation_rate": round(activation_rate, 4),
            "nudge_response_rate": round(nudge_rate, 4),
            "reactivations_last_90d": reactivations,
            "classification": classification,
        })

    # Sort by activation rate descending
    rankings.sort(key=lambda r: r["activation_rate"], reverse=True)
    avg_rate = total_activation_rate / len(adm_users) if adm_users else 0.0

    return {
        "adm_rankings": rankings,
        "top_5_adms": rankings[:5],
        "bottom_5_adms": rankings[-5:] if len(rankings) > 5 else rankings,
        "average_activation_rate": round(avg_rate, 4),
    }


# ─── Training Effectiveness ───


async def get_training_effectiveness(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> dict:
    """Compute training module effectiveness metrics.

    Returns dict matching TrainingEffectivenessResponse schema.
    """
    now = datetime.now(timezone.utc)
    ninety_days_ago = now - timedelta(days=90)

    # Get all training interaction signals
    result = await db.execute(
        select(Signal).where(
            Signal.tenant_id == tenant_id,
            Signal.signal_type == SignalType.WHATSAPP_TRAINING_INTERACTION,
            Signal.timestamp >= ninety_days_ago,
            Signal.agent_id.isnot(None),
        )
    )
    training_signals = list(result.scalars().all())

    # Track per-module: started, completed, scores
    module_started: dict[str, set[uuid.UUID]] = defaultdict(set)
    module_completed: dict[str, set[uuid.UUID]] = defaultdict(set)
    module_scores: dict[str, list[float]] = defaultdict(list)
    agent_completed_modules: dict[uuid.UUID, list[tuple[str, datetime]]] = defaultdict(list)

    for sig in training_signals:
        payload = sig.payload or {}
        module_id = payload.get("module_id", "unknown")
        agent_id = sig.agent_id
        if not agent_id:
            continue

        module_started[module_id].add(agent_id)

        interaction_type = payload.get("interaction_type", "")
        completion_pct = payload.get("completion_percentage", 0)
        quiz_score = payload.get("quiz_score")

        if interaction_type == "QUIZ_COMPLETED" or (completion_pct and float(completion_pct) >= 80):
            module_completed[module_id].add(agent_id)
            agent_completed_modules[agent_id].append((module_id, sig.timestamp))

        if quiz_score is not None:
            module_scores[module_id].append(float(quiz_score))

    # Completion rates
    completion_rates = {}
    for module_id in module_started:
        started = len(module_started[module_id])
        completed = len(module_completed.get(module_id, set()))
        completion_rates[module_id] = round(completed / started, 4) if started > 0 else 0.0

    # Average scores
    avg_scores = {}
    for module_id, scores in module_scores.items():
        avg_scores[module_id] = round(sum(scores) / len(scores), 2) if scores else 0.0

    # Training-to-sale correlation:
    # For each module, find agents who completed it, then check if they had
    # a POLICY_SOLD signal within 30 days after completion
    sale_signals_result = await db.execute(
        select(Signal).where(
            Signal.tenant_id == tenant_id,
            Signal.signal_type == SignalType.POLICY_SOLD,
            Signal.timestamp >= ninety_days_ago,
            Signal.agent_id.isnot(None),
        )
    )
    sale_signals = list(sale_signals_result.scalars().all())
    agent_sale_dates: dict[uuid.UUID, list[datetime]] = defaultdict(list)
    for sig in sale_signals:
        if sig.agent_id:
            agent_sale_dates[sig.agent_id].append(sig.timestamp)

    training_to_sale: dict[str, float] = {}
    for module_id in module_completed:
        completed_agents = module_completed[module_id]
        if not completed_agents:
            training_to_sale[module_id] = 0.0
            continue
        sold_within_30d = 0
        for agent_id in completed_agents:
            # Find completion date for this module
            completions = [
                (m, d) for m, d in agent_completed_modules.get(agent_id, [])
                if m == module_id
            ]
            if not completions:
                continue
            completion_date = completions[0][1]
            # Check if agent sold within 30 days
            sale_dates = agent_sale_dates.get(agent_id, [])
            for sd in sale_dates:
                if completion_date <= sd <= completion_date + timedelta(days=30):
                    sold_within_30d += 1
                    break
        training_to_sale[module_id] = round(
            sold_within_30d / len(completed_agents), 4
        ) if completed_agents else 0.0

    # Drop-off modules (high start, low completion)
    drop_off = []
    for module_id in module_started:
        started = len(module_started[module_id])
        completed = len(module_completed.get(module_id, set()))
        if started >= 3:  # Minimum sample size
            drop_off_rate = 1 - (completed / started)
            drop_off.append((module_id, drop_off_rate))
    drop_off.sort(key=lambda x: x[1], reverse=True)
    top_drop_off = [m for m, _ in drop_off[:5]]

    return {
        "completion_rate_by_module": completion_rates,
        "average_scores_by_module": avg_scores,
        "training_to_sale_correlation": training_to_sale,
        "top_drop_off_modules": top_drop_off,
    }


# ─── System ROI ───


async def get_system_roi(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    period_days: int = 30,
    system_cost: float = 50000.0,  # Default estimated cost, tenant-configurable
) -> dict:
    """Compute system ROI.

    Returns dict matching SystemROIResponse schema.
    """
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=period_days)

    # Find reactivated agents (DORMANT -> ACTIVE/FIRST_SALE)
    lifecycle_result = await db.execute(
        select(Signal).where(
            Signal.tenant_id == tenant_id,
            Signal.signal_type == SignalType.LIFECYCLE_STATE_CHANGED,
            Signal.timestamp >= period_start,
        )
    )
    reactivated_agent_ids: set[uuid.UUID] = set()
    for sig in lifecycle_result.scalars().all():
        payload = sig.payload or {}
        if (
            payload.get("previous_state") == AgentLifecycleState.DORMANT
            and payload.get("new_state") in (
                AgentLifecycleState.ACTIVE,
                AgentLifecycleState.FIRST_SALE,
            )
            and sig.agent_id
        ):
            reactivated_agent_ids.add(sig.agent_id)

    # Sum premium from POLICY_SOLD signals for reactivated agents
    total_premium = 0.0
    if reactivated_agent_ids:
        sale_result = await db.execute(
            select(Signal).where(
                Signal.tenant_id == tenant_id,
                Signal.signal_type == SignalType.POLICY_SOLD,
                Signal.agent_id.in_(reactivated_agent_ids),
                Signal.timestamp >= period_start,
            )
        )
        for sig in sale_result.scalars().all():
            payload = sig.payload or {}
            premium = payload.get("premium", {})
            if isinstance(premium, dict):
                total_premium += float(premium.get("amount", 0))
            elif isinstance(premium, (int, float)):
                total_premium += float(premium)

    agents_reactivated = len(reactivated_agent_ids)
    avg_premium = total_premium / agents_reactivated if agents_reactivated > 0 else 0.0
    roi = total_premium / system_cost if system_cost > 0 else 0.0

    return {
        "new_premium_from_reactivated": round(total_premium, 2),
        "system_cost_this_month": system_cost,
        "roi_multiplier": round(roi, 2),
        "agents_reactivated": agents_reactivated,
        "average_premium_per_reactivation": round(avg_premium, 2),
    }
