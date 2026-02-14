"""tasks/adm_briefing.py — Celery tasks for ADM briefing generation.

Uses SYNC sessions (psycopg2) — Celery workers are synchronous.
Scheduled via Celery beat:
- Morning briefings: daily at 02:00 UTC (07:30 IST)
- Weekly summaries: Monday at 02:30 UTC (08:00 IST)
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, func

from config.celery_app import celery_app
from config.database import sync_session_factory
from core.enums import AgentLifecycleState, SignalType, UserRole
from modules.adm.models import MorningBriefing, WeeklySummary
from modules.agent.models import Agent
from modules.signal.models import Signal
from modules.user.models import User

logger = logging.getLogger(__name__)

MAX_PRIORITY_AGENTS = 5


@celery_app.task(name="tasks.adm_briefing.generate_morning_briefings")
def generate_morning_briefings() -> dict:
    """Generate morning briefings for all ADMs across all tenants.

    Runs daily at 02:00 UTC. Uses sync session.
    """
    today = date.today()
    generated = 0
    errors = 0

    with sync_session_factory() as session:
        # Find all active ADMs
        result = session.execute(
            select(User).where(
                User.roles.any(UserRole.ADM),
                User.deleted_at.is_(None),
            )
        )
        adms = list(result.scalars().all())

        for adm in adms:
            try:
                # Check if briefing already exists for today (idempotent)
                existing = session.execute(
                    select(func.count()).select_from(MorningBriefing).where(
                        MorningBriefing.tenant_id == adm.tenant_id,
                        MorningBriefing.adm_id == adm.id,
                        MorningBriefing.briefing_date == today,
                    )
                )
                if existing.scalar() > 0:
                    continue

                _generate_briefing_sync(session, adm.tenant_id, adm.id, today)
                generated += 1
            except Exception:
                logger.exception("Error generating briefing for ADM %s", adm.id)
                errors += 1

        session.commit()

    logger.info("Morning briefings generated: %d, errors: %d", generated, errors)
    return {"generated": generated, "errors": errors}


@celery_app.task(name="tasks.adm_briefing.generate_weekly_summaries")
def generate_weekly_summaries() -> dict:
    """Generate weekly summaries for all ADMs across all tenants.

    Runs Monday at 02:30 UTC. Uses sync session.
    """
    today = date.today()
    week_start = today - timedelta(days=today.weekday() + 7)  # Previous Monday
    week_end = week_start + timedelta(days=6)  # Previous Sunday
    generated = 0
    errors = 0

    with sync_session_factory() as session:
        result = session.execute(
            select(User).where(
                User.roles.any(UserRole.ADM),
                User.deleted_at.is_(None),
            )
        )
        adms = list(result.scalars().all())

        for adm in adms:
            try:
                # Check if summary already exists (idempotent)
                existing = session.execute(
                    select(func.count()).select_from(WeeklySummary).where(
                        WeeklySummary.tenant_id == adm.tenant_id,
                        WeeklySummary.adm_id == adm.id,
                        WeeklySummary.week_start == week_start,
                    )
                )
                if existing.scalar() > 0:
                    continue

                _generate_weekly_sync(session, adm.tenant_id, adm.id, week_start, week_end)
                generated += 1
            except Exception:
                logger.exception("Error generating weekly summary for ADM %s", adm.id)
                errors += 1

        session.commit()

    logger.info("Weekly summaries generated: %d, errors: %d", generated, errors)
    return {"generated": generated, "errors": errors}


def _generate_briefing_sync(
    session, tenant_id: uuid.UUID, adm_id: uuid.UUID, today: date
) -> None:
    """Generate a single morning briefing synchronously."""
    # Get agents
    result = session.execute(
        select(Agent).where(
            Agent.tenant_id == tenant_id,
            Agent.assigned_adm_id == adm_id,
            Agent.deleted_at.is_(None),
        )
    )
    agents = list(result.scalars().all())

    # Compute snapshot
    active = sum(1 for a in agents if a.lifecycle_state in (
        AgentLifecycleState.ACTIVE, AgentLifecycleState.PRODUCTIVE, AgentLifecycleState.FIRST_SALE
    ))
    at_risk = sum(1 for a in agents if a.lifecycle_state == AgentLifecycleState.AT_RISK)
    dormant = sum(1 for a in agents if a.lifecycle_state == AgentLifecycleState.DORMANT)

    # Priority agents (simplified for sync)
    now = datetime.now(timezone.utc)
    priorities = []
    for agent in agents:
        if len(priorities) >= MAX_PRIORITY_AGENTS:
            break
        if agent.license_expiry_date:
            days_to_expiry = (agent.license_expiry_date - now).days
            if 0 < days_to_expiry <= 45:
                priorities.append({
                    "agent_id": str(agent.id),
                    "agent_name": agent.full_name,
                    "one_line_context": f"License expiring in {days_to_expiry} days",
                    "suggested_action": "Help complete training hours for renewal",
                    "priority_emoji": "\U0001f534",
                })

    for agent in agents:
        if len(priorities) >= MAX_PRIORITY_AGENTS:
            break
        if agent.lifecycle_state == AgentLifecycleState.AT_RISK:
            if any(p["agent_id"] == str(agent.id) for p in priorities):
                continue
            days_in_state = (now - agent.state_since).days if agent.state_since else 0
            priorities.append({
                "agent_id": str(agent.id),
                "agent_name": agent.full_name,
                "one_line_context": f"At-risk for {days_in_state} days",
                "suggested_action": "Check in — find out what's happening",
                "priority_emoji": "\U0001f7e1",
            })

    content = {
        "snapshot": {
            "active_count": active,
            "at_risk_count": at_risk,
            "at_risk_change": 0,
            "dormant_count": dormant,
        },
        "priorities": priorities,
        "celebrations": [],
    }

    briefing = MorningBriefing(
        tenant_id=tenant_id,
        adm_id=adm_id,
        briefing_date=today,
        content=content,
    )
    session.add(briefing)


def _generate_weekly_sync(
    session, tenant_id: uuid.UUID, adm_id: uuid.UUID,
    week_start: date, week_end: date,
) -> None:
    """Generate a single weekly summary synchronously."""
    result = session.execute(
        select(Agent).where(
            Agent.tenant_id == tenant_id,
            Agent.assigned_adm_id == adm_id,
            Agent.deleted_at.is_(None),
        )
    )
    agents = list(result.scalars().all())
    agent_ids = [a.id for a in agents]

    ws_dt = datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc)
    we_dt = datetime.combine(week_end, datetime.max.time(), tzinfo=timezone.utc)

    # Wins
    wins = []
    if agent_ids:
        sales_result = session.execute(
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
                wins.append({
                    "agent_name": agent.full_name,
                    "achievement": f"Policy sold — {sig.payload.get('product_name', 'policy')}",
                })

    # Movement
    movement = {"newly_active_count": 0, "newly_at_risk_count": 0, "reengaged_count": 0}
    if agent_ids:
        lifecycle_result = session.execute(
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
                movement["newly_active_count"] += 1
            if new_state == AgentLifecycleState.AT_RISK:
                movement["newly_at_risk_count"] += 1
            if prev_state == AgentLifecycleState.DORMANT and new_state != AgentLifecycleState.DORMANT:
                movement["reengaged_count"] += 1

    content = {
        "wins": wins,
        "movement": movement,
        "adm_numbers": {"agents_contacted": 0, "system_assisted_contacts": 0, "training_completions": 0},
        "focus_areas": [],
    }

    summary = WeeklySummary(
        tenant_id=tenant_id,
        adm_id=adm_id,
        week_start=week_start,
        week_end=week_end,
        content=content,
    )
    session.add(summary)
