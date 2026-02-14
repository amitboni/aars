"""tasks/signal_processing.py — Celery tasks for signal processing (slow path).

Uses SYNC sessions (psycopg2) — Celery workers are synchronous.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from config.celery_app import celery_app
from config.database import sync_session_factory
from core.tenant_context import set_rls_context_sync
from modules.agent.lifecycle import compute_transition, is_positive_signal
from modules.agent.models import Agent
from modules.signal.models import Signal
from core.enums import SignalType

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.signal_processing.process_pending_signals")
def process_pending_signals() -> dict:
    """SLOW PATH: Pick up unprocessed signals and process them.

    Runs every 60 seconds via Celery beat.
    Catches signals missed by fast path (batch imports, crash recovery).
    Idempotent — safe to process the same signal multiple times.
    """
    with sync_session_factory() as session:
        result = session.execute(
            select(Signal)
            .where(Signal.processed.is_(False))
            .order_by(Signal.created_at.asc())
            .limit(100)
        )
        signals = list(result.scalars().all())

        if not signals:
            return {"processed": 0}

        processed_count = 0
        for signal in signals:
            try:
                _process_signal_sync(session, signal)
                processed_count += 1
            except Exception:
                logger.exception("Error processing signal %s", signal.id)
                session.rollback()
                continue

        session.commit()
        logger.info("Slow path processed %d signals", processed_count)
        return {"processed": processed_count}


def _process_signal_sync(session, signal: Signal) -> None:
    """Process a single signal synchronously (for Celery)."""
    if signal.processed:
        return

    agent = None
    if signal.agent_id:
        result = session.execute(
            select(Agent).where(
                Agent.id == signal.agent_id,
                Agent.deleted_at.is_(None),
            )
        )
        agent = result.scalar_one_or_none()

    if agent:
        # Update agent understanding
        contact_signals = {
            SignalType.VOICE_CALL_OUTCOME,
            SignalType.WHATSAPP_AGENT_REPLIED,
            SignalType.WHATSAPP_MESSAGE_SENT,
            SignalType.ADM_AGENT_CALL_LOGGED,
            SignalType.ADM_AGENT_VISIT_LOGGED,
        }
        if signal.signal_type in contact_signals:
            agent.last_contact_at = signal.timestamp

        if is_positive_signal(signal.signal_type, signal.payload):
            agent.last_positive_signal_at = signal.timestamp

        if signal.signal_type == SignalType.POLICY_SOLD:
            agent.total_policies_sold = (agent.total_policies_sold or 0) + 1
            agent.policies_sold_last_12m = (agent.policies_sold_last_12m or 0) + 1

        # Check lifecycle transition
        new_state = compute_transition(
            current_state=agent.lifecycle_state,
            signal_type=signal.signal_type,
            payload=signal.payload,
            agent=agent,
        )
        if new_state:
            previous_state = agent.lifecycle_state
            agent.lifecycle_state = new_state
            agent.state_since = datetime.now(timezone.utc)

            if previous_state == "dormant" and new_state != "dormant":
                agent.dormancy_reason = None

            logger.info(
                "Agent %s lifecycle: %s → %s (slow path, signal %s)",
                agent.id, previous_state, new_state, signal.id,
            )

            # Emit lifecycle_state_changed signal
            lifecycle_signal = Signal(
                tenant_id=agent.tenant_id,
                signal_type=SignalType.LIFECYCLE_STATE_CHANGED,
                source="system",
                agent_id=agent.id,
                timestamp=datetime.now(timezone.utc),
                payload={
                    "previous_state": previous_state,
                    "new_state": new_state,
                    "trigger_signal_id": str(signal.id),
                    "reason": f"Triggered by {signal.signal_type} (slow path)",
                },
                metadata_={},
                processed=True,
                processed_at=datetime.now(timezone.utc),
            )
            session.add(lifecycle_signal)

    signal.processed = True
    signal.processed_at = datetime.now(timezone.utc)
