"""modules/adm/briefing.py — Morning briefing and weekly summary generation.

Per spec section 3.4.1 (Morning Briefing) and 3.4.4 (Weekly Summary).
Priority selection: URGENT first, then OPPORTUNITIES, then CELEBRATIONS.
Max 5 agents per briefing to reduce cognitive load.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import AgentLifecycleState, SignalType
from modules.adm.models import MorningBriefing, WeeklySummary
from modules.adm.schemas import (
    ADMNumbers,
    BriefingCelebration,
    BriefingPriority,
    BriefingSnapshot,
    MorningBriefingResponse,
    WeeklyMovement,
    WeeklySummaryResponse,
    WeeklyWin,
)
from modules.agent.models import Agent
from modules.signal.models import Signal

logger = logging.getLogger(__name__)

MAX_PRIORITY_AGENTS = 5


async def generate_morning_briefing(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    adm_id: uuid.UUID,
    briefing_date: date | None = None,
) -> MorningBriefingResponse:
    """Generate a morning briefing for an ADM.

    Steps:
    1. Query agents assigned to this ADM
    2. Compute snapshot (active, at_risk, dormant counts)
    3. Compare at_risk vs 7 days ago
    4. Select priority agents (max 5)
    5. Include celebrations
    """
    today = briefing_date or date.today()

    # 1. Get all agents assigned to this ADM
    result = await db.execute(
        select(Agent).where(
            Agent.tenant_id == tenant_id,
            Agent.assigned_adm_id == adm_id,
            Agent.deleted_at.is_(None),
        )
    )
    agents = list(result.scalars().all())

    # 2. Compute snapshot
    snapshot = _compute_snapshot(agents)

    # 3. Compare at_risk vs 7 days ago — count agents that were at_risk 7 days ago
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    at_risk_7d_ago_result = await db.execute(
        select(func.count()).select_from(Signal).where(
            Signal.tenant_id == tenant_id,
            Signal.signal_type == SignalType.LIFECYCLE_STATE_CHANGED,
            Signal.timestamp >= seven_days_ago,
            Signal.payload["new_state"].astext == AgentLifecycleState.AT_RISK,
        )
    )
    new_at_risk_count = at_risk_7d_ago_result.scalar() or 0
    snapshot.at_risk_change = new_at_risk_count  # net new at-risk in past 7 days

    # 4. Select priority agents
    priorities = await _select_priorities(db, tenant_id, agents, today)

    # 5. Get celebrations (recent sales + training completions)
    celebrations = await _get_celebrations(db, tenant_id, adm_id, today)

    # Store briefing
    content = {
        "snapshot": snapshot.model_dump(),
        "priorities": [p.model_dump(mode="json") for p in priorities],
        "celebrations": [c.model_dump(mode="json") for c in celebrations],
    }
    briefing = MorningBriefing(
        tenant_id=tenant_id,
        adm_id=adm_id,
        briefing_date=today,
        content=content,
    )
    db.add(briefing)
    await db.flush()

    return MorningBriefingResponse(
        id=briefing.id,
        adm_id=adm_id,
        briefing_date=today,
        snapshot=snapshot,
        priorities=priorities,
        celebrations=celebrations,
    )


async def generate_weekly_summary(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    adm_id: uuid.UUID,
    week_start: date | None = None,
    week_end: date | None = None,
) -> WeeklySummaryResponse:
    """Generate a weekly summary for an ADM.

    Per spec section 3.4.4: wins, movement, ADM numbers, focus areas.
    """
    today = date.today()
    ws = week_start or (today - timedelta(days=today.weekday() + 7))
    we = week_end or (ws + timedelta(days=6))
    ws_dt = datetime.combine(ws, datetime.min.time(), tzinfo=timezone.utc)
    we_dt = datetime.combine(we, datetime.max.time(), tzinfo=timezone.utc)

    agents_result = await db.execute(
        select(Agent).where(
            Agent.tenant_id == tenant_id,
            Agent.assigned_adm_id == adm_id,
            Agent.deleted_at.is_(None),
        )
    )
    agents = list(agents_result.scalars().all())
    agent_ids = [a.id for a in agents]

    # Wins: POLICY_SOLD signals this week
    wins: list[WeeklyWin] = []
    if agent_ids:
        sales_result = await db.execute(
            select(Signal).where(
                Signal.tenant_id == tenant_id,
                Signal.signal_type == SignalType.POLICY_SOLD,
                Signal.agent_id.in_(agent_ids),
                Signal.timestamp.between(ws_dt, we_dt),
            )
        )
        for sig in sales_result.scalars().all():
            agent = next((a for a in agents if a.id == sig.agent_id), None)
            if agent:
                wins.append(WeeklyWin(
                    agent_name=agent.full_name,
                    achievement=f"Policy sold — {sig.payload.get('product_name', 'policy')}",
                ))

        # Training completions
        training_result = await db.execute(
            select(Signal).where(
                Signal.tenant_id == tenant_id,
                Signal.signal_type == SignalType.WHATSAPP_TRAINING_INTERACTION,
                Signal.agent_id.in_(agent_ids),
                Signal.timestamp.between(ws_dt, we_dt),
                Signal.payload["interaction_type"].astext == "QUIZ_COMPLETED",
            )
        )
        for sig in training_result.scalars().all():
            agent = next((a for a in agents if a.id == sig.agent_id), None)
            if agent:
                score = sig.payload.get("quiz_score", 0)
                wins.append(WeeklyWin(
                    agent_name=agent.full_name,
                    achievement=f"Training completed (Score: {score:.0f}%)",
                ))

    # Movement: lifecycle state changes this week
    movement = WeeklyMovement()
    if agent_ids:
        lifecycle_result = await db.execute(
            select(Signal).where(
                Signal.tenant_id == tenant_id,
                Signal.signal_type == SignalType.LIFECYCLE_STATE_CHANGED,
                Signal.agent_id.in_(agent_ids),
                Signal.timestamp.between(ws_dt, we_dt),
            )
        )
        for sig in lifecycle_result.scalars().all():
            new_state = sig.payload.get("new_state", "")
            prev_state = sig.payload.get("previous_state", "")
            if new_state == AgentLifecycleState.ACTIVE:
                movement.newly_active_count += 1
            if new_state == AgentLifecycleState.AT_RISK:
                movement.newly_at_risk_count += 1
            if prev_state == AgentLifecycleState.DORMANT and new_state != AgentLifecycleState.DORMANT:
                movement.reengaged_count += 1

    # ADM numbers
    adm_numbers = ADMNumbers()
    if agent_ids:
        # ADM contacts (calls + visits)
        adm_contacts_result = await db.execute(
            select(func.count()).select_from(Signal).where(
                Signal.tenant_id == tenant_id,
                Signal.signal_type.in_([
                    SignalType.ADM_AGENT_CALL_LOGGED,
                    SignalType.ADM_AGENT_VISIT_LOGGED,
                ]),
                Signal.adm_id == adm_id,
                Signal.timestamp.between(ws_dt, we_dt),
            )
        )
        adm_numbers.agents_contacted = adm_contacts_result.scalar() or 0

        # System-assisted contacts (WhatsApp + Voice)
        system_contacts_result = await db.execute(
            select(func.count()).select_from(Signal).where(
                Signal.tenant_id == tenant_id,
                Signal.signal_type.in_([
                    SignalType.WHATSAPP_MESSAGE_SENT,
                    SignalType.VOICE_CALL_OUTCOME,
                ]),
                Signal.agent_id.in_(agent_ids),
                Signal.timestamp.between(ws_dt, we_dt),
            )
        )
        adm_numbers.system_assisted_contacts = system_contacts_result.scalar() or 0

        # Training completions
        training_count_result = await db.execute(
            select(func.count()).select_from(Signal).where(
                Signal.tenant_id == tenant_id,
                Signal.signal_type == SignalType.WHATSAPP_TRAINING_INTERACTION,
                Signal.agent_id.in_(agent_ids),
                Signal.timestamp.between(ws_dt, we_dt),
                Signal.payload["interaction_type"].astext == "QUIZ_COMPLETED",
            )
        )
        adm_numbers.training_completions = training_count_result.scalar() or 0

    # Focus areas: top 3 agents needing attention
    focus_areas = _compute_focus_areas(agents)

    content = {
        "wins": [w.model_dump() for w in wins],
        "movement": movement.model_dump(),
        "adm_numbers": adm_numbers.model_dump(),
        "focus_areas": focus_areas,
    }
    summary = WeeklySummary(
        tenant_id=tenant_id,
        adm_id=adm_id,
        week_start=ws,
        week_end=we,
        content=content,
    )
    db.add(summary)
    await db.flush()

    return WeeklySummaryResponse(
        id=summary.id,
        adm_id=adm_id,
        week_start=ws,
        week_end=we,
        wins=wins,
        movement=movement,
        adm_numbers=adm_numbers,
        focus_areas=focus_areas,
    )


def _compute_snapshot(agents: list[Agent]) -> BriefingSnapshot:
    """Count agents by lifecycle state."""
    active = sum(1 for a in agents if a.lifecycle_state in (
        AgentLifecycleState.ACTIVE, AgentLifecycleState.PRODUCTIVE, AgentLifecycleState.FIRST_SALE
    ))
    at_risk = sum(1 for a in agents if a.lifecycle_state == AgentLifecycleState.AT_RISK)
    dormant = sum(1 for a in agents if a.lifecycle_state == AgentLifecycleState.DORMANT)
    return BriefingSnapshot(
        active_count=active,
        at_risk_count=at_risk,
        dormant_count=dormant,
    )


async def _select_priorities(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    agents: list[Agent],
    today: date,
) -> list[BriefingPriority]:
    """Select up to MAX_PRIORITY_AGENTS priority agents.

    Order: URGENT (license expiring) → OPPORTUNITY (reactivation signals) → AT_RISK.
    """
    priorities: list[BriefingPriority] = []

    # 1. URGENT: license expiring within 45 days
    now = datetime.now(timezone.utc)
    for agent in agents:
        if len(priorities) >= MAX_PRIORITY_AGENTS:
            break
        if agent.license_expiry_date:
            days_to_expiry = (agent.license_expiry_date - now).days
            if 0 < days_to_expiry <= 45:
                priorities.append(BriefingPriority(
                    agent_id=agent.id,
                    agent_name=agent.full_name,
                    one_line_context=f"License expiring in {days_to_expiry} days",
                    suggested_action="Help complete training hours for renewal",
                    priority_emoji="🔴",
                ))

    # 2. OPPORTUNITY: dormant agents with recent positive signals (last 7 days)
    seven_days_ago = now - timedelta(days=7)
    dormant_agents = [a for a in agents if a.lifecycle_state == AgentLifecycleState.DORMANT]
    for agent in dormant_agents:
        if len(priorities) >= MAX_PRIORITY_AGENTS:
            break
        if agent.id in [p.agent_id for p in priorities]:
            continue
        if agent.last_positive_signal_at and agent.last_positive_signal_at >= seven_days_ago:
            priorities.append(BriefingPriority(
                agent_id=agent.id,
                agent_name=agent.full_name,
                one_line_context="Re-engagement signal detected — responded recently",
                suggested_action="Call now — reactivation window is open",
                priority_emoji="🟢",
            ))

    # 3. AT_RISK agents
    at_risk_agents = [a for a in agents if a.lifecycle_state == AgentLifecycleState.AT_RISK]
    for agent in at_risk_agents:
        if len(priorities) >= MAX_PRIORITY_AGENTS:
            break
        if agent.id in [p.agent_id for p in priorities]:
            continue
        days_in_state = (now - agent.state_since).days if agent.state_since else 0
        priorities.append(BriefingPriority(
            agent_id=agent.id,
            agent_name=agent.full_name,
            one_line_context=f"At-risk for {days_in_state} days",
            suggested_action="Check in — find out what's happening",
            priority_emoji="🟡",
        ))

    return priorities[:MAX_PRIORITY_AGENTS]


async def _get_celebrations(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    adm_id: uuid.UUID,
    today: date,
) -> list[BriefingCelebration]:
    """Get recent celebrations for ADM's agents (last 3 days)."""
    three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)

    # Get agent IDs assigned to this ADM
    agent_result = await db.execute(
        select(Agent.id, Agent.full_name).where(
            Agent.tenant_id == tenant_id,
            Agent.assigned_adm_id == adm_id,
            Agent.deleted_at.is_(None),
        )
    )
    agent_map = {row[0]: row[1] for row in agent_result.all()}
    if not agent_map:
        return []

    celebrations: list[BriefingCelebration] = []

    # Sales
    sales_result = await db.execute(
        select(Signal).where(
            Signal.tenant_id == tenant_id,
            Signal.signal_type == SignalType.POLICY_SOLD,
            Signal.agent_id.in_(list(agent_map.keys())),
            Signal.timestamp >= three_days_ago,
        ).limit(3)
    )
    for sig in sales_result.scalars().all():
        name = agent_map.get(sig.agent_id, "Agent")
        celebrations.append(BriefingCelebration(
            agent_id=sig.agent_id,
            agent_name=name,
            achievement=f"Policy sold — {sig.payload.get('product_name', 'new policy')}",
        ))

    return celebrations


def _compute_focus_areas(agents: list[Agent]) -> list[str]:
    """Compute top 3 focus areas for next week."""
    areas: list[str] = []

    # Count at-risk agents
    at_risk = [a for a in agents if a.lifecycle_state == AgentLifecycleState.AT_RISK]
    if at_risk:
        areas.append(f"{len(at_risk)} agents at-risk — check in and find out why")

    # Count dormant agents with recent contact
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    reengaging = [
        a for a in agents
        if a.lifecycle_state == AgentLifecycleState.DORMANT
        and a.last_positive_signal_at
        and a.last_positive_signal_at >= seven_days_ago
    ]
    if reengaging:
        areas.append(f"{len(reengaging)} dormant agents showing interest — follow up quickly")

    # License expiring
    expiring = [
        a for a in agents
        if a.license_expiry_date and 0 < (a.license_expiry_date - now).days <= 60
    ]
    if expiring:
        areas.append(f"{len(expiring)} agents with licenses expiring soon")

    if not areas:
        areas.append("Continue regular engagement with active agents")

    return areas[:3]
