"""tasks/decision_engine.py — Celery tasks for Decision Engine.

Uses SYNC sessions (psycopg2) — Celery workers are synchronous.

Two tasks:
  decision_engine_batch       — daily at 01:00 UTC (before briefings at 02:00)
  execute_pending_decisions   — every 60 seconds
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func

from config.celery_app import celery_app
from config.database import sync_session_factory
from core.enums import DecisionAction, SignalType
from modules.agent.models import Agent
from modules.decision.constraints import run_all_constraints
from modules.decision.models import DecisionLog
from modules.decision.rules import evaluate_rules
from modules.decision.schemas import DecisionInput, DecisionOutput
from modules.playbook.models import PlaybookRun
from modules.signal.models import Signal
from modules.tenant.models import Tenant

logger = logging.getLogger(__name__)

# Evaluation cadence (mirrors engine.py)
_CADENCE: dict[str, int] = {
    "onboarded": 1, "licensed": 2, "first_sale": 3,
    "active": 7, "productive": 14, "at_risk": 1, "dormant": 7,
}


@celery_app.task(name="tasks.decision_engine.decision_engine_batch")
def decision_engine_batch() -> dict:
    """Daily batch evaluation of all agents across all active tenants.

    Runs at 01:00 UTC — before morning briefings at 02:00 UTC.
    """
    with sync_session_factory() as session:
        result = session.execute(
            select(Tenant.id).where(Tenant.is_active.is_(True))
        )
        tenant_ids = [row[0] for row in result.all()]

        total_evaluated = 0
        for tenant_id in tenant_ids:
            try:
                count = _batch_evaluate_tenant_sync(session, tenant_id)
                total_evaluated += count
                session.commit()
            except Exception:
                logger.exception("Batch evaluation failed for tenant %s", tenant_id)
                session.rollback()

        logger.info(
            "Batch evaluation complete: %d agents across %d tenants",
            total_evaluated, len(tenant_ids),
        )
        return {"tenants": len(tenant_ids), "evaluated": total_evaluated}


def _batch_evaluate_tenant_sync(session, tenant_id) -> int:
    """Evaluate all eligible agents for a tenant (sync, for Celery)."""
    now = datetime.now(timezone.utc)

    agents = list(
        session.execute(
            select(Agent).where(
                Agent.tenant_id == tenant_id,
                Agent.deleted_at.is_(None),
            )
        ).scalars().all()
    )

    evaluated = 0
    for agent in agents:
        if agent.lifecycle_state in ("lapsed", "terminated"):
            continue

        cadence_days = _CADENCE.get(agent.lifecycle_state, 7)

        last_eval = session.execute(
            select(DecisionLog.created_at)
            .where(
                DecisionLog.agent_id == agent.id,
                DecisionLog.tenant_id == tenant_id,
            )
            .order_by(DecisionLog.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        if last_eval and (now - last_eval).days < cadence_days:
            continue

        try:
            inp = _build_input_sync(session, agent, tenant_id, now)
            decision = evaluate_rules(inp)
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
                        reasoning=f"Blocked: {constraint.reason} (original: {decision.action})",
                    )

            if decision.language is None:
                decision.language = agent.preferred_language

            log = DecisionLog(
                tenant_id=tenant_id,
                agent_id=agent.id,
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
            session.add(log)
            session.flush()
            evaluated += 1
        except Exception:
            logger.exception("Failed to evaluate agent %s", agent.id)

    return evaluated


def _build_input_sync(session, agent: Agent, tenant_id, now: datetime) -> DecisionInput:
    """Build DecisionInput synchronously for Celery."""
    days_in_state = (now - agent.state_since).days if agent.state_since else 0

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    contacts_count = session.execute(
        select(func.count()).select_from(Signal).where(
            Signal.agent_id == agent.id,
            Signal.tenant_id == tenant_id,
            Signal.signal_type.in_([
                SignalType.VOICE_CALL_OUTCOME,
                SignalType.WHATSAPP_MESSAGE_SENT,
                SignalType.ADM_AGENT_CALL_LOGGED,
                SignalType.ADM_AGENT_VISIT_LOGGED,
            ]),
            Signal.timestamp >= month_start,
        )
    ).scalar() or 0

    active_pb = session.execute(
        select(PlaybookRun.playbook_id).where(
            PlaybookRun.agent_id == agent.id,
            PlaybookRun.tenant_id == tenant_id,
            PlaybookRun.status == "in_progress",
        ).limit(1)
    ).scalar_one_or_none()

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
        active_playbook_id=active_pb,
        contacts_this_month=contacts_count,
    )


@celery_app.task(name="tasks.decision_engine.execute_pending_decisions")
def execute_pending_decisions() -> dict:
    """Execute pending decisions whose scheduled_time has passed.

    Runs every 60 seconds via Celery beat.
    """
    with sync_session_factory() as session:
        now = datetime.now(timezone.utc)
        result = session.execute(
            select(DecisionLog).where(
                DecisionLog.executed.is_(False),
                DecisionLog.scheduled_time <= now,
                DecisionLog.decision_action != DecisionAction.DO_NOTHING,
            )
            .order_by(DecisionLog.scheduled_time.asc())
            .limit(50)
        )
        logs = list(result.scalars().all())

        if not logs:
            return {"executed": 0}

        executed = 0
        for log in logs:
            try:
                _execute_decision_sync(session, log)
                executed += 1
            except Exception:
                logger.exception("Error executing decision %s", log.id)
                session.rollback()

        session.commit()
        logger.info("Executed %d pending decisions", executed)
        return {"executed": executed}


def _execute_decision_sync(session, log: DecisionLog) -> None:
    """Execute a single decision synchronously (for Celery)."""
    now = datetime.now(timezone.utc)
    execution_result: dict = {"status": "success"}

    try:
        action = log.decision_action

        if action == DecisionAction.SEND_NUDGE_TO_ADM:
            if log.adm_id:
                from modules.adm.models import ADMAlert
                alert = ADMAlert(
                    tenant_id=log.tenant_id,
                    adm_id=log.adm_id,
                    agent_id=log.agent_id,
                    alert_type="DECISION_ENGINE",
                    urgency=log.priority,
                    message=log.reasoning,
                )
                session.add(alert)
                session.flush()
                execution_result = {"status": "success", "alert_id": str(alert.id)}
            else:
                execution_result = {"status": "skipped", "reason": "No ADM assigned"}

        elif action in (
            DecisionAction.SCHEDULE_VOICE_CALL,
            DecisionAction.SEND_WHATSAPP,
            DecisionAction.SEND_TRAINING,
            DecisionAction.CELEBRATE,
        ):
            execution_result = {
                "status": "queued",
                "channel": log.channel or "unknown",
                "agent_id": str(log.agent_id),
            }

        elif action == DecisionAction.ESCALATE:
            execution_result = {"status": "escalated", "agent_id": str(log.agent_id)}

        elif action == DecisionAction.PAUSE_OUTREACH:
            execution_result = {"status": "paused", "agent_id": str(log.agent_id)}

        elif action == DecisionAction.CLOSE_AND_ARCHIVE:
            execution_result = {"status": "archived", "agent_id": str(log.agent_id)}

        else:
            execution_result = {"status": "completed", "action": action}

    except Exception as e:
        execution_result = {"status": "error", "error": str(e)}

    log.executed = True
    log.executed_at = now
    log.execution_result = execution_result
