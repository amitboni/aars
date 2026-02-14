"""modules/playbook/executor.py — Playbook step execution logic."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


async def execute_step(db: AsyncSession, run: PlaybookRun) -> PlaybookStepRun | None:
    """Execute the current step of a playbook run.

    Returns the step run record, or None if no step could be executed.
    """
    if run.status != "in_progress":
        return None

    # Load the playbook and find the current step
    result = await db.execute(
        select(Playbook).where(Playbook.id == run.playbook_id)
    )
    playbook = result.scalar_one_or_none()
    if not playbook:
        logger.error("Playbook %s not found for run %s", run.playbook_id, run.id)
        run.status = "failed"
        await db.flush()
        return None

    # Find current step
    step = _find_step(playbook.steps, run.current_step_number)
    if not step:
        logger.info(
            "No step %d in playbook %s — completing run %s",
            run.current_step_number, playbook.id, run.id,
        )
        await _complete_run(db, run, "completed", "NO_RESPONSE")
        return None

    # Check max duration
    if _is_expired(run, playbook):
        await _complete_run(db, run, "expired", "EXPIRED")
        return None

    # Execute the step action
    outcome = await _execute_action(db, run, step)

    # Record step execution
    step_run = PlaybookStepRun(
        playbook_run_id=run.id,
        playbook_step_id=step.id,
        step_number=step.step_number,
        status="completed",
        executed_at=datetime.now(timezone.utc),
        outcome=outcome.get("outcome"),
        outcome_details=outcome,
    )

    # Resolve branching
    branch_context = {**run.context, **outcome}
    resolved = resolve_next_step(step.next_step_rules, branch_context)

    if resolved:
        if resolved.get("action") == "CLOSE_PLAYBOOK":
            step_run.next_step_number = None
            db.add(step_run)
            close_outcome = resolved.get("outcome", "NO_RESPONSE")
            await _complete_run(db, run, "completed", close_outcome)
            return step_run

        next_step_num = resolved.get("go_to_step")
        if next_step_num is not None:
            step_run.next_step_number = next_step_num
        else:
            # Default: next sequential step
            step_run.next_step_number = step.step_number + 1
    else:
        # No rules matched — advance to next sequential step
        step_run.next_step_number = step.step_number + 1

    db.add(step_run)

    # Update run state
    run.steps_executed = (run.steps_executed or 0) + 1
    run.context = {**run.context, **outcome}

    # Check if next step exists
    next_step = _find_step(playbook.steps, step_run.next_step_number)
    if next_step:
        run.current_step_number = next_step.step_number
        run.next_step_due_at = datetime.now(timezone.utc) + timedelta(
            days=next_step.delay_days
        )
    else:
        # No more steps — playbook completed
        await _complete_run(db, run, "completed", "AGENT_ENGAGED")
        return step_run

    # Emit PLAYBOOK_STEP_EXECUTED signal
    signal = Signal(
        tenant_id=run.tenant_id,
        signal_type=SignalType.PLAYBOOK_STEP_EXECUTED,
        source="system",
        agent_id=run.agent_id,
        timestamp=datetime.now(timezone.utc),
        payload={
            "playbook_id": str(run.playbook_id),
            "step_number": step.step_number,
            "step_action": step.action_type,
            "outcome": outcome.get("outcome"),
        },
        metadata_={},
        processed=True,
        processed_at=datetime.now(timezone.utc),
    )
    db.add(signal)

    await db.flush()
    return step_run


async def _execute_action(
    db: AsyncSession, run: PlaybookRun, step: PlaybookStep
) -> dict:
    """Execute a step's action. Returns outcome dict.

    Currently uses mock implementations for channel integrations.
    Real implementations will call voice AI, WhatsApp, etc.
    """
    action_type = step.action_type
    config = step.action_config

    if action_type == "voice_call":
        return {
            "outcome": "executed",
            "action": "voice_call",
            "purpose": config.get("purpose", "check_in"),
            "status": "scheduled",
        }
    elif action_type == "whatsapp_message":
        return {
            "outcome": "executed",
            "action": "whatsapp_message",
            "template": config.get("message_template", ""),
            "status": "sent",
        }
    elif action_type == "whatsapp_training":
        return {
            "outcome": "executed",
            "action": "whatsapp_training",
            "module": config.get("training_module", ""),
            "status": "sent",
        }
    elif action_type == "adm_nudge":
        # Emit ADM_NUDGE_RECEIVED signal so ADM gets notified
        from modules.agent.models import Agent

        agent_result = await db.execute(
            select(Agent).where(Agent.id == run.agent_id)
        )
        agent = agent_result.scalar_one_or_none()
        adm_id = agent.assigned_adm_id if agent else None

        nudge_signal = Signal(
            tenant_id=run.tenant_id,
            signal_type=SignalType.ADM_NUDGE_RECEIVED,
            source="system",
            agent_id=run.agent_id,
            adm_id=adm_id,
            timestamp=datetime.now(timezone.utc),
            payload={
                "playbook_id": str(run.playbook_id),
                "nudge_message": config.get("nudge_message_template", ""),
                "nudge_type": config.get("nudge_type", "playbook_step"),
                "step_number": step.step_number,
            },
            metadata_={},
            processed=True,
            processed_at=datetime.now(timezone.utc),
        )
        db.add(nudge_signal)

        return {
            "outcome": "executed",
            "action": "adm_nudge",
            "message": config.get("nudge_message_template", ""),
            "adm_id": str(adm_id) if adm_id else None,
            "status": "sent",
        }
    elif action_type == "wait":
        return {
            "outcome": "waited",
            "action": "wait",
            "days": config.get("days", step.delay_days),
        }
    elif action_type == "escalate":
        return {
            "outcome": "escalated",
            "action": "escalate",
            "reason": config.get("reason", ""),
        }
    else:
        logger.warning("Unknown action type: %s", action_type)
        return {"outcome": "unknown_action", "action": action_type}


def _find_step(steps: list[PlaybookStep], step_number: int) -> PlaybookStep | None:
    """Find a step by step_number in the steps list."""
    for step in steps:
        if step.step_number == step_number:
            return step
    return None


def _is_expired(run: PlaybookRun, playbook: Playbook) -> bool:
    """Check if the run has exceeded max_duration_days."""
    elapsed = datetime.now(timezone.utc) - run.started_at
    return elapsed.days > playbook.max_duration_days


async def _complete_run(
    db: AsyncSession,
    run: PlaybookRun,
    status: str,
    outcome: str,
) -> None:
    """Complete a playbook run and emit the completion signal."""
    run.status = status
    run.outcome = outcome
    run.completed_at = datetime.now(timezone.utc)
    run.next_step_due_at = None

    # Emit PLAYBOOK_COMPLETED signal
    signal = Signal(
        tenant_id=run.tenant_id,
        signal_type=SignalType.PLAYBOOK_COMPLETED,
        source="system",
        agent_id=run.agent_id,
        timestamp=datetime.now(timezone.utc),
        payload={
            "playbook_id": str(run.playbook_id),
            "outcome": outcome,
            "duration_days": (datetime.now(timezone.utc) - run.started_at).days,
            "steps_executed": run.steps_executed or 0,
        },
        metadata_={},
        processed=True,
        processed_at=datetime.now(timezone.utc),
    )
    db.add(signal)
    await db.flush()

    logger.info(
        "Playbook run %s completed: status=%s outcome=%s steps=%d",
        run.id, status, outcome, run.steps_executed or 0,
    )
