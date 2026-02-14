"""tasks/playbook_execution.py — Celery tasks for playbook step execution (sync).

Uses SYNC sessions (psycopg2) — Celery workers are synchronous.
Runs every minute via Celery beat to execute due playbook steps.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from config.celery_app import celery_app
from config.database import sync_session_factory
from core.enums import SignalType
from modules.playbook.condition_evaluator import resolve_next_step
from modules.playbook.models import (
    Playbook,
    PlaybookRun,
    PlaybookStep,
    PlaybookStepRun,
)
from modules.signal.models import Signal

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.playbook_execution.execute_due_playbook_steps")
def execute_due_playbook_steps() -> dict:
    """Execute playbook steps that are due (next_step_due_at <= now).

    Idempotent: safe to retry. Checks step hasn't already been executed.
    """
    now = datetime.now(timezone.utc)
    executed = 0
    expired = 0

    with sync_session_factory() as session:
        result = session.execute(
            select(PlaybookRun)
            .where(
                PlaybookRun.status == "in_progress",
                PlaybookRun.next_step_due_at <= now,
            )
            .limit(50)
        )
        runs = list(result.scalars().all())

        if not runs:
            return {"executed": 0, "expired": 0}

        for run in runs:
            try:
                was_expired = _execute_run_step_sync(session, run, now)
                if was_expired:
                    expired += 1
                else:
                    executed += 1
            except Exception:
                logger.exception("Error executing step for run %s", run.id)
                session.rollback()
                continue

        session.commit()
        logger.info("Playbook execution: executed=%d expired=%d", executed, expired)

    return {"executed": executed, "expired": expired}


def _execute_run_step_sync(session, run: PlaybookRun, now: datetime) -> bool:
    """Execute one step of a playbook run synchronously. Returns True if expired."""
    # Load playbook
    result = session.execute(
        select(Playbook).where(Playbook.id == run.playbook_id)
    )
    playbook = result.scalar_one_or_none()
    if not playbook:
        run.status = "failed"
        return False

    # Check expiry
    elapsed = now - run.started_at
    if elapsed.days > playbook.max_duration_days:
        run.status = "expired"
        run.outcome = "EXPIRED"
        run.completed_at = now
        run.next_step_due_at = None
        _emit_completion_signal_sync(session, run, "EXPIRED")
        return True

    # Find current step
    step = None
    for s in playbook.steps:
        if s.step_number == run.current_step_number:
            step = s
            break

    if not step:
        run.status = "completed"
        run.outcome = "NO_RESPONSE"
        run.completed_at = now
        run.next_step_due_at = None
        _emit_completion_signal_sync(session, run, "NO_RESPONSE")
        return False

    # Execute action (mock for now, except adm_nudge which emits signal)
    outcome = _execute_action_sync(session, run, step)

    # Record step run
    step_run = PlaybookStepRun(
        playbook_run_id=run.id,
        playbook_step_id=step.id,
        step_number=step.step_number,
        status="completed",
        executed_at=now,
        outcome=outcome.get("outcome"),
        outcome_details=outcome,
    )

    # Resolve branching
    branch_context = {**run.context, **outcome}
    resolved = resolve_next_step(step.next_step_rules, branch_context)

    if resolved and resolved.get("action") == "CLOSE_PLAYBOOK":
        step_run.next_step_number = None
        session.add(step_run)
        run.status = "completed"
        run.outcome = resolved.get("outcome", "NO_RESPONSE")
        run.completed_at = now
        run.next_step_due_at = None
        run.steps_executed = (run.steps_executed or 0) + 1
        _emit_completion_signal_sync(session, run, run.outcome)
        return False

    next_step_num = (resolved.get("go_to_step") if resolved else None) or (step.step_number + 1)
    step_run.next_step_number = next_step_num
    session.add(step_run)

    run.steps_executed = (run.steps_executed or 0) + 1
    run.context = {**run.context, **outcome}

    # Find next step
    next_step = None
    for s in playbook.steps:
        if s.step_number == next_step_num:
            next_step = s
            break

    if next_step:
        run.current_step_number = next_step.step_number
        run.next_step_due_at = now + timedelta(days=next_step.delay_days)
    else:
        run.status = "completed"
        run.outcome = "AGENT_ENGAGED"
        run.completed_at = now
        run.next_step_due_at = None
        _emit_completion_signal_sync(session, run, "AGENT_ENGAGED")

    # Emit step executed signal
    signal = Signal(
        tenant_id=run.tenant_id,
        signal_type=SignalType.PLAYBOOK_STEP_EXECUTED,
        source="system",
        agent_id=run.agent_id,
        timestamp=now,
        payload={
            "playbook_id": str(run.playbook_id),
            "step_number": step.step_number,
            "step_action": step.action_type,
            "outcome": outcome.get("outcome"),
        },
        metadata_={},
        processed=True,
        processed_at=now,
    )
    session.add(signal)
    return False


def _execute_action_sync(session, run: PlaybookRun, step: PlaybookStep) -> dict:
    """Execute a step action synchronously (mock implementation).

    For adm_nudge actions, emits ADM_NUDGE_RECEIVED signal.
    """
    config = step.action_config

    if step.action_type == "adm_nudge":
        from modules.agent.models import Agent

        agent_result = session.execute(
            select(Agent).where(Agent.id == run.agent_id)
        )
        agent = agent_result.scalar_one_or_none()
        adm_id = agent.assigned_adm_id if agent else None
        now = datetime.now(timezone.utc)

        nudge_signal = Signal(
            tenant_id=run.tenant_id,
            signal_type=SignalType.ADM_NUDGE_RECEIVED,
            source="system",
            agent_id=run.agent_id,
            adm_id=adm_id,
            timestamp=now,
            payload={
                "playbook_id": str(run.playbook_id),
                "nudge_message": config.get("nudge_message_template", ""),
                "nudge_type": config.get("nudge_type", "playbook_step"),
                "step_number": step.step_number,
            },
            metadata_={},
            processed=True,
            processed_at=now,
        )
        session.add(nudge_signal)

        return {
            "outcome": "executed",
            "action": "adm_nudge",
            "message": config.get("nudge_message_template", ""),
            "adm_id": str(adm_id) if adm_id else None,
            "status": "sent",
        }

    return {
        "outcome": "executed",
        "action": step.action_type,
        "status": "sent",
    }


def _emit_completion_signal_sync(session, run: PlaybookRun, outcome: str) -> None:
    """Emit a PLAYBOOK_COMPLETED signal synchronously."""
    now = datetime.now(timezone.utc)
    signal = Signal(
        tenant_id=run.tenant_id,
        signal_type=SignalType.PLAYBOOK_COMPLETED,
        source="system",
        agent_id=run.agent_id,
        timestamp=now,
        payload={
            "playbook_id": str(run.playbook_id),
            "outcome": outcome,
            "duration_days": (now - run.started_at).days,
            "steps_executed": run.steps_executed or 0,
        },
        metadata_={},
        processed=True,
        processed_at=now,
    )
    session.add(signal)
