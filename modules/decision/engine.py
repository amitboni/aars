"""modules/decision/engine.py — Decision evaluation and execution.

Core functions:
  evaluate_agent   — evaluate one agent, log decision
  batch_evaluate   — evaluate all eligible agents (cadence-aware)
  execute_decision — map DecisionAction → service calls
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import DecisionAction, SignalType
from modules.agent.models import Agent
from modules.decision.constraints import run_all_constraints
from modules.decision.models import DecisionLog
from modules.decision.rules import evaluate_rules
from modules.decision.schemas import DecisionInput, DecisionOutput
from modules.playbook.models import PlaybookRun
from modules.signal.models import Signal

logger = logging.getLogger(__name__)

# Evaluation cadence by lifecycle state (days between evaluations)
EVALUATION_CADENCE: dict[str, int] = {
    "onboarded": 1,
    "licensed": 2,
    "first_sale": 3,
    "active": 7,
    "productive": 14,
    "at_risk": 1,
    "dormant": 7,
    # lapsed, terminated → never evaluated (blocked by terminal constraint)
}


async def build_decision_input(
    db: AsyncSession, agent: Agent, tenant_id: uuid.UUID,
) -> DecisionInput:
    """Build DecisionInput from an Agent model and related data."""
    now = datetime.now(timezone.utc)

    days_in_state = 0
    if agent.state_since:
        days_in_state = (now - agent.state_since).days

    # Count contacts this month
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    contact_types = [
        SignalType.VOICE_CALL_OUTCOME,
        SignalType.WHATSAPP_MESSAGE_SENT,
        SignalType.ADM_AGENT_CALL_LOGGED,
        SignalType.ADM_AGENT_VISIT_LOGGED,
    ]
    contacts_result = await db.execute(
        select(func.count()).select_from(Signal).where(
            Signal.agent_id == agent.id,
            Signal.tenant_id == tenant_id,
            Signal.signal_type.in_(contact_types),
            Signal.timestamp >= month_start,
        )
    )
    contacts_this_month = contacts_result.scalar() or 0

    # Check for active playbook run
    active_run = await db.execute(
        select(PlaybookRun.playbook_id).where(
            PlaybookRun.agent_id == agent.id,
            PlaybookRun.tenant_id == tenant_id,
            PlaybookRun.status == "in_progress",
        ).limit(1)
    )
    active_playbook_id = active_run.scalar_one_or_none()

    return DecisionInput(
        agent_id=agent.id,
        tenant_id=tenant_id,
        lifecycle_state=agent.lifecycle_state,
        days_in_state=days_in_state,
        engagement_score=agent.engagement_score or 0.0,
        last_positive_signal_at=agent.last_positive_signal_at,
        last_contact_at=agent.last_contact_at,
        consent={
            "voice": agent.consent_voice or "not_asked",
            "whatsapp": agent.consent_whatsapp or "not_asked",
        },
        dormancy_reason=agent.dormancy_reason,
        total_policies=agent.total_policies_sold or 0,
        license_expiry_date=agent.license_expiry_date,
        adm_id=agent.assigned_adm_id,
        active_playbook_id=active_playbook_id,
        contacts_this_month=contacts_this_month,
    )


async def evaluate_agent(
    db: AsyncSession, agent_id: uuid.UUID, tenant_id: uuid.UUID,
) -> DecisionLog:
    """Evaluate a single agent and log the decision.

    1. Load agent
    2. Build DecisionInput
    3. Evaluate rules (first match wins)
    4. Run constraints against proposed action
    5. Log and return DecisionLog
    """
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.tenant_id == tenant_id,
            Agent.deleted_at.is_(None),
        )
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise ValueError(f"Agent {agent_id} not found in tenant {tenant_id}")

    inp = await build_decision_input(db, agent, tenant_id)
    decision = evaluate_rules(inp)

    # Run constraints against the proposed action
    now = datetime.now(timezone.utc)
    constraint = run_all_constraints(inp, decision.channel, decision.scheduled_time)

    if not constraint.allowed:
        if constraint.defer_to:
            decision = DecisionOutput(
                action=decision.action,
                rule_id=decision.rule_id,
                playbook_id=decision.playbook_id,
                scheduled_time=constraint.defer_to,
                channel=decision.channel,
                language=decision.language,
                priority=decision.priority,
                reasoning=f"{decision.reasoning} [DEFERRED: {constraint.reason}]",
            )
        else:
            decision = DecisionOutput(
                action=DecisionAction.DO_NOTHING,
                rule_id=decision.rule_id,
                scheduled_time=now,
                priority=decision.priority,
                reasoning=f"Blocked by constraint: {constraint.reason} (original: {decision.action})",
            )

    if decision.language is None:
        decision.language = agent.preferred_language

    log = DecisionLog(
        tenant_id=tenant_id,
        agent_id=agent_id,
        adm_id=agent.assigned_adm_id,
        rule_id=decision.rule_id,
        decision_action=decision.action,
        playbook_id=decision.playbook_id,
        channel=decision.channel,
        language=decision.language,
        priority=decision.priority,
        reasoning=decision.reasoning,
        scheduled_time=decision.scheduled_time,
    )
    db.add(log)
    await db.flush()

    logger.info(
        "Decision for agent %s: %s (rule=%s, priority=%s)",
        agent_id, decision.action, decision.rule_id, decision.priority,
    )
    return log


async def batch_evaluate(
    db: AsyncSession, tenant_id: uuid.UUID,
) -> list[DecisionLog]:
    """Evaluate all eligible agents for a tenant.

    Respects evaluation cadence — not every agent is evaluated daily.
    """
    now = datetime.now(timezone.utc)
    results: list[DecisionLog] = []

    agent_result = await db.execute(
        select(Agent).where(
            Agent.tenant_id == tenant_id,
            Agent.deleted_at.is_(None),
        )
    )
    agents = list(agent_result.scalars().all())

    for agent in agents:
        if agent.lifecycle_state in ("lapsed", "terminated"):
            continue

        cadence_days = EVALUATION_CADENCE.get(agent.lifecycle_state, 7)

        last_decision = await db.execute(
            select(DecisionLog.created_at)
            .where(
                DecisionLog.agent_id == agent.id,
                DecisionLog.tenant_id == tenant_id,
            )
            .order_by(DecisionLog.created_at.desc())
            .limit(1)
        )
        last_evaluated_at = last_decision.scalar_one_or_none()

        if last_evaluated_at and (now - last_evaluated_at).days < cadence_days:
            continue

        try:
            log = await evaluate_agent(db, agent.id, tenant_id)
            results.append(log)
        except Exception:
            logger.exception("Failed to evaluate agent %s", agent.id)

    logger.info(
        "Batch evaluation for tenant %s: %d agents evaluated",
        tenant_id, len(results),
    )
    return results


async def execute_decision(
    db: AsyncSession, decision_log_id: uuid.UUID, tenant_id: uuid.UUID,
) -> DecisionLog:
    """Execute a pending decision by mapping DecisionAction to service calls."""
    result = await db.execute(
        select(DecisionLog).where(
            DecisionLog.id == decision_log_id,
            DecisionLog.tenant_id == tenant_id,
        )
    )
    log = result.scalar_one_or_none()
    if not log:
        raise ValueError(f"DecisionLog {decision_log_id} not found")

    if log.executed:
        return log

    now = datetime.now(timezone.utc)
    execution_result: dict = {"status": "success"}

    try:
        action = log.decision_action

        if action == DecisionAction.DO_NOTHING:
            execution_result = {"status": "skipped", "reason": "DO_NOTHING"}

        elif action == DecisionAction.START_PLAYBOOK:
            if log.playbook_id:
                from modules.playbook.schemas import PlaybookTrigger
                from modules.playbook.service import trigger_playbook
                trigger = PlaybookTrigger(
                    playbook_id=log.playbook_id,
                    agent_id=log.agent_id,
                    context={"trigger_reason": f"decision_engine:{log.rule_id}"},
                )
                run = await trigger_playbook(db, tenant_id, trigger)
                execution_result = {"status": "success", "playbook_run_id": str(run.id)}
            else:
                execution_result = {"status": "skipped", "reason": "No playbook_id specified"}

        elif action == DecisionAction.SEND_NUDGE_TO_ADM:
            if log.adm_id:
                from modules.adm import alerts as alerts_service
                alert = await alerts_service.create_alert(
                    db, tenant_id, log.adm_id, log.agent_id,
                    alert_type="DECISION_ENGINE",
                    urgency=log.priority,
                    message=log.reasoning,
                )
                execution_result = {"status": "success", "alert_id": str(alert.id)}
            else:
                execution_result = {"status": "skipped", "reason": "No ADM assigned"}

        elif action == DecisionAction.SCHEDULE_VOICE_CALL:
            execution_result = {
                "status": "queued", "channel": "voice_ai",
                "agent_id": str(log.agent_id),
            }

        elif action == DecisionAction.SEND_WHATSAPP:
            execution_result = {
                "status": "queued", "channel": "whatsapp_bot",
                "agent_id": str(log.agent_id),
            }

        elif action == DecisionAction.SEND_TRAINING:
            execution_result = {
                "status": "queued", "channel": "whatsapp_bot",
                "type": "training", "agent_id": str(log.agent_id),
            }

        elif action == DecisionAction.ESCALATE:
            execution_result = {"status": "escalated", "agent_id": str(log.agent_id)}

        elif action == DecisionAction.CELEBRATE:
            execution_result = {
                "status": "queued", "channel": "whatsapp_bot",
                "type": "celebration", "agent_id": str(log.agent_id),
            }

        elif action == DecisionAction.PAUSE_OUTREACH:
            execution_result = {"status": "paused", "agent_id": str(log.agent_id)}

        elif action == DecisionAction.CLOSE_AND_ARCHIVE:
            execution_result = {"status": "archived", "agent_id": str(log.agent_id)}

        elif action == DecisionAction.CONTINUE_PLAYBOOK:
            execution_result = {"status": "continued", "agent_id": str(log.agent_id)}

        else:
            execution_result = {"status": "unknown_action", "action": action}

    except Exception as e:
        execution_result = {"status": "error", "error": str(e)}
        logger.exception("Error executing decision %s", decision_log_id)

    log.executed = True
    log.executed_at = now
    log.execution_result = execution_result
    await db.flush()

    return log
