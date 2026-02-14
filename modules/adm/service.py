"""modules/adm/service.py — ADM service: agent detail, listing, effectiveness.

Per spec sections 3.4.2 (Agent Detail), 2.9 (ADM Effectiveness classification).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import AgentLifecycleState, SignalType
from modules.adm.schemas import (
    ADMEffectivenessResponse,
    AgentDetailResponse,
    EffectivenessStats,
    EngagementStats,
    PortfolioStats,
    QuickAction,
    RecentSignalSummary,
)
from modules.agent.models import Agent
from modules.signal.models import Signal

logger = logging.getLogger(__name__)


async def get_agent_detail_for_adm(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    adm_id: uuid.UUID,
    agent_id: uuid.UUID,
) -> AgentDetailResponse | None:
    """Get detailed agent view for an ADM.

    Per spec section 3.4.2: recent signals, system recommendation, quick actions.
    """
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.tenant_id == tenant_id,
            Agent.assigned_adm_id == adm_id,
            Agent.deleted_at.is_(None),
        )
    )
    agent = result.scalar_one_or_none()
    if not agent:
        return None

    now = datetime.now(timezone.utc)

    # Days in current state
    days_in_state = (now - agent.state_since).days if agent.state_since else 0

    # Last contact info
    last_contact_date = None
    last_contact_channel = None
    if agent.last_contact_at:
        last_contact_date = agent.last_contact_at.strftime("%Y-%m-%d")
        # Get channel from most recent contact signal
        contact_result = await db.execute(
            select(Signal.channel).where(
                Signal.tenant_id == tenant_id,
                Signal.agent_id == agent_id,
                Signal.signal_type.in_([
                    SignalType.VOICE_CALL_OUTCOME,
                    SignalType.WHATSAPP_AGENT_REPLIED,
                    SignalType.ADM_AGENT_CALL_LOGGED,
                    SignalType.ADM_AGENT_VISIT_LOGGED,
                ]),
            ).order_by(Signal.timestamp.desc()).limit(1)
        )
        last_contact_channel = contact_result.scalar_one_or_none()

    # Recent signals (last 14 days, max 10)
    fourteen_days_ago = now - timedelta(days=14)
    signals_result = await db.execute(
        select(Signal).where(
            Signal.tenant_id == tenant_id,
            Signal.agent_id == agent_id,
            Signal.timestamp >= fourteen_days_ago,
        ).order_by(Signal.timestamp.desc()).limit(10)
    )
    recent_signals = [
        RecentSignalSummary(
            date=sig.timestamp.strftime("%Y-%m-%d"),
            channel=sig.channel or sig.source,
            summary=_signal_summary(sig),
        )
        for sig in signals_result.scalars().all()
    ]

    # System recommendation
    recommendation = _compute_recommendation(agent, days_in_state)

    # Quick actions
    quick_actions = _get_quick_actions(agent)

    return AgentDetailResponse(
        agent_id=agent.id,
        agent_name=agent.full_name,
        lifecycle_state=agent.lifecycle_state,
        days_in_state=days_in_state,
        last_contact_date=last_contact_date,
        last_contact_channel=last_contact_channel,
        recent_signals=recent_signals,
        system_recommendation=recommendation,
        quick_actions=quick_actions,
    )


async def list_adm_agents(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    adm_id: uuid.UUID,
    lifecycle_state: str | None = None,
    limit: int = 50,
    cursor: uuid.UUID | None = None,
) -> tuple[list[Agent], uuid.UUID | None]:
    """List agents assigned to an ADM with optional lifecycle filter."""
    query = (
        select(Agent)
        .where(
            Agent.tenant_id == tenant_id,
            Agent.assigned_adm_id == adm_id,
            Agent.deleted_at.is_(None),
        )
        .order_by(Agent.full_name, Agent.id)
        .limit(limit + 1)
    )
    if lifecycle_state:
        query = query.where(Agent.lifecycle_state == lifecycle_state)
    if cursor:
        cursor_agent = await db.get(Agent, cursor)
        if cursor_agent:
            query = query.where(
                (Agent.full_name > cursor_agent.full_name)
                | (
                    (Agent.full_name == cursor_agent.full_name)
                    & (Agent.id > cursor_agent.id)
                )
            )

    result = await db.execute(query)
    agents = list(result.scalars().all())

    next_cursor = None
    if len(agents) > limit:
        agents = agents[:limit]
        next_cursor = agents[-1].id

    return agents, next_cursor


async def compute_adm_effectiveness(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    adm_id: uuid.UUID,
) -> ADMEffectivenessResponse:
    """Compute ADM effectiveness metrics and classification.

    Classification thresholds (per spec section 2.9):
    - HIGH_PERFORMER: activation_rate > 10% AND nudge_response_rate > 0.7
    - AVERAGE: activation_rate 3-10%
    - STRUGGLING: activation_rate < 3% AND nudge_response_rate > 0.3
    - UNRESPONSIVE: nudge_response_rate < 0.2
    """
    now = datetime.now(timezone.utc)

    # Portfolio stats
    agents_result = await db.execute(
        select(Agent).where(
            Agent.tenant_id == tenant_id,
            Agent.assigned_adm_id == adm_id,
            Agent.deleted_at.is_(None),
        )
    )
    agents = list(agents_result.scalars().all())
    agent_ids = [a.id for a in agents]

    agents_by_state: dict[str, int] = {}
    for agent in agents:
        state = agent.lifecycle_state
        agents_by_state[state] = agents_by_state.get(state, 0) + 1

    # Activation rate = agents who reached first_sale or beyond / total
    activated_states = {
        AgentLifecycleState.FIRST_SALE,
        AgentLifecycleState.ACTIVE,
        AgentLifecycleState.PRODUCTIVE,
    }
    activated_count = sum(1 for a in agents if a.lifecycle_state in activated_states)
    activation_rate = (activated_count / len(agents)) if agents else 0.0

    portfolio = PortfolioStats(
        total_agents=len(agents),
        agents_by_state=agents_by_state,
        activation_rate=round(activation_rate, 4),
    )

    # Engagement stats
    thirty_days_ago = now - timedelta(days=30)
    engagement = EngagementStats()

    if agent_ids:
        # Agents contacted last 30 days
        contacted_result = await db.execute(
            select(func.count(func.distinct(Signal.agent_id))).where(
                Signal.tenant_id == tenant_id,
                Signal.signal_type.in_([
                    SignalType.ADM_AGENT_CALL_LOGGED,
                    SignalType.ADM_AGENT_VISIT_LOGGED,
                ]),
                Signal.adm_id == adm_id,
                Signal.agent_id.in_(agent_ids),
                Signal.timestamp >= thirty_days_ago,
            )
        )
        engagement.agents_contacted_last_30d = contacted_result.scalar() or 0

        # Nudges received
        nudges_received_result = await db.execute(
            select(func.count()).select_from(Signal).where(
                Signal.tenant_id == tenant_id,
                Signal.signal_type == SignalType.ADM_NUDGE_RECEIVED,
                Signal.adm_id == adm_id,
                Signal.timestamp >= thirty_days_ago,
            )
        )
        engagement.nudges_received = nudges_received_result.scalar() or 0

        # Nudges acted on
        nudges_acted_result = await db.execute(
            select(func.count()).select_from(Signal).where(
                Signal.tenant_id == tenant_id,
                Signal.signal_type == SignalType.ADM_NUDGE_ACTED_ON,
                Signal.adm_id == adm_id,
                Signal.timestamp >= thirty_days_ago,
            )
        )
        engagement.nudges_acted_on = nudges_acted_result.scalar() or 0

        if engagement.nudges_received > 0:
            engagement.nudge_response_rate = round(
                engagement.nudges_acted_on / engagement.nudges_received, 4
            )

        # Average time to act (from nudge payload)
        acted_signals_result = await db.execute(
            select(Signal.payload).where(
                Signal.tenant_id == tenant_id,
                Signal.signal_type == SignalType.ADM_NUDGE_ACTED_ON,
                Signal.adm_id == adm_id,
                Signal.timestamp >= thirty_days_ago,
            )
        )
        time_values = []
        for row in acted_signals_result.all():
            t = (row[0] or {}).get("time_to_action_minutes")
            if t is not None:
                time_values.append(t)
        if time_values:
            engagement.average_time_to_act_hours = round(
                sum(time_values) / len(time_values) / 60, 2
            )

    # Effectiveness stats (90 days)
    ninety_days_ago = now - timedelta(days=90)
    effectiveness = EffectivenessStats()

    if agent_ids:
        # Reactivations: dormant -> non-dormant transitions
        reactivation_result = await db.execute(
            select(func.count()).select_from(Signal).where(
                Signal.tenant_id == tenant_id,
                Signal.signal_type == SignalType.LIFECYCLE_STATE_CHANGED,
                Signal.agent_id.in_(agent_ids),
                Signal.timestamp >= ninety_days_ago,
                Signal.payload["previous_state"].astext == AgentLifecycleState.DORMANT,
                Signal.payload["new_state"].astext != AgentLifecycleState.DORMANT,
            )
        )
        effectiveness.reactivations_last_90d = reactivation_result.scalar() or 0

        # First sales facilitated
        first_sale_result = await db.execute(
            select(func.count()).select_from(Signal).where(
                Signal.tenant_id == tenant_id,
                Signal.signal_type == SignalType.LIFECYCLE_STATE_CHANGED,
                Signal.agent_id.in_(agent_ids),
                Signal.timestamp >= ninety_days_ago,
                Signal.payload["new_state"].astext == AgentLifecycleState.FIRST_SALE,
            )
        )
        effectiveness.first_sales_facilitated_last_90d = first_sale_result.scalar() or 0

    # Classification
    classification, reason = _classify_adm(
        activation_rate, engagement.nudge_response_rate
    )

    return ADMEffectivenessResponse(
        adm_id=adm_id,
        portfolio=portfolio,
        engagement=engagement,
        effectiveness=effectiveness,
        classification=classification,
        classification_reason=reason,
    )


def _signal_summary(signal: Signal) -> str:
    """Generate a human-readable summary for a signal."""
    summaries = {
        SignalType.VOICE_CALL_OUTCOME: lambda s: f"Voice call — {s.payload.get('outcome', 'completed')}",
        SignalType.WHATSAPP_MESSAGE_SENT: lambda s: f"WhatsApp sent — {s.payload.get('template_name', 'message')}",
        SignalType.WHATSAPP_AGENT_REPLIED: lambda s: "Agent replied via WhatsApp",
        SignalType.WHATSAPP_TRAINING_INTERACTION: lambda s: f"Training — {s.payload.get('interaction_type', 'interaction')}",
        SignalType.POLICY_SOLD: lambda s: f"Policy sold — {s.payload.get('product_name', 'policy')}",
        SignalType.ADM_AGENT_CALL_LOGGED: lambda s: f"ADM called — {s.payload.get('outcome', 'logged')}",
        SignalType.ADM_AGENT_VISIT_LOGGED: lambda s: f"ADM visited — {s.payload.get('visit_purpose', 'visit')}",
        SignalType.LIFECYCLE_STATE_CHANGED: lambda s: f"State changed: {s.payload.get('previous_state', '?')} → {s.payload.get('new_state', '?')}",
        SignalType.CONSENT_CHANGED: lambda s: f"Consent updated — {s.payload.get('consent_type', 'consent')}",
    }
    formatter = summaries.get(signal.signal_type)
    if formatter:
        return formatter(signal)
    return signal.signal_type.replace("_", " ").title()


def _compute_recommendation(agent: Agent, days_in_state: int) -> str:
    """Generate system recommendation based on agent state."""
    state = agent.lifecycle_state

    if state == AgentLifecycleState.DORMANT:
        if agent.last_positive_signal_at:
            now = datetime.now(timezone.utc)
            days_since = (now - agent.last_positive_signal_at).days
            if days_since <= 7:
                return "Re-engagement window open — call now while interest is fresh"
        return "Dormant agent — try a personal call to understand what's happening"

    if state == AgentLifecycleState.AT_RISK:
        if days_in_state > 30:
            return "At-risk for over a month — consider an in-person visit"
        return "Recently at-risk — a timely call can prevent dormancy"

    if state == AgentLifecycleState.ONBOARDED:
        if days_in_state > 14:
            return "Onboarded but no progress — help with first steps"
        return "New agent — help them get licensed and started"

    if state == AgentLifecycleState.LICENSED:
        return "Licensed but no sale yet — focus on first-sale coaching"

    if state == AgentLifecycleState.FIRST_SALE:
        return "First sale done — celebrate and build momentum"

    if state in (AgentLifecycleState.ACTIVE, AgentLifecycleState.PRODUCTIVE):
        return "Performing well — continue regular engagement"

    return "Keep in touch and monitor progress"


def _get_quick_actions(agent: Agent) -> list[QuickAction]:
    """Get available quick actions based on agent state."""
    actions = [
        QuickAction(id="call", label="Log Call"),
        QuickAction(id="visit", label="Log Visit"),
    ]

    state = agent.lifecycle_state
    if state in (AgentLifecycleState.DORMANT, AgentLifecycleState.AT_RISK):
        actions.append(QuickAction(id="training", label="Send Training"))

    if state == AgentLifecycleState.DORMANT:
        actions.append(QuickAction(id="escalate", label="Escalate"))

    return actions


def _classify_adm(
    activation_rate: float,
    nudge_response_rate: float,
) -> tuple[str, str]:
    """Classify ADM performance.

    Thresholds per spec section 2.9:
    - HIGH_PERFORMER: activation > 10% AND response > 70%
    - AVERAGE: activation 3-10%
    - STRUGGLING: activation < 3% AND response > 30%
    - UNRESPONSIVE: response < 20%
    """
    if nudge_response_rate < 0.2:
        return "UNRESPONSIVE", "Nudge response rate below 20%"

    if activation_rate > 0.10 and nudge_response_rate > 0.7:
        return "HIGH_PERFORMER", "Strong activation rate with excellent nudge responsiveness"

    if activation_rate >= 0.03:
        return "AVERAGE", "Moderate activation rate — room for improvement"

    if nudge_response_rate > 0.3:
        return "STRUGGLING", "Low activation rate but responsive to nudges — needs support"

    return "AVERAGE", "Below-average activation — focus on agent engagement"
