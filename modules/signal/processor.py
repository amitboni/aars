"""modules/signal/processor.py — Signal processing: lifecycle transitions + understanding updates."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import SignalType
from core.events import SignalReceived, LifecycleStateChanged, event_bus
from modules.agent.lifecycle import compute_transition, is_positive_signal
from modules.agent.models import Agent
from modules.signal.models import Signal
from modules.adm import alerts as adm_alerts
from modules.signal.schemas import SignalEmit

logger = logging.getLogger(__name__)


async def process_signal(db: AsyncSession, signal: Signal) -> None:
    """Process a single signal: run lifecycle check, update agent understanding.

    Idempotent — processing the same signal twice is harmless.
    """
    if signal.processed:
        return

    agent = None
    if signal.agent_id:
        result = await db.execute(
            select(Agent).where(
                Agent.id == signal.agent_id,
                Agent.deleted_at.is_(None),
            )
        )
        agent = result.scalar_one_or_none()

    if agent:
        # Capture pre-transition state for alert trigger check
        pre_transition_state = agent.lifecycle_state

        # Update agent understanding
        await _update_agent_understanding(db, agent, signal)

        # Check lifecycle transition
        await _check_lifecycle_transition(db, agent, signal)

        # Auto-create ADM alerts from specific signal patterns
        # Use pre-transition state so dormant->active transitions still trigger alerts
        await _check_adm_alert_triggers(db, agent, signal, pre_transition_state)

        # Trigger immediate decision evaluation for high-priority signals
        await _trigger_immediate_evaluation(db, agent, signal, pre_transition_state)

    # Mark processed
    signal.processed = True
    signal.processed_at = datetime.now(timezone.utc)
    await db.flush()


async def _update_agent_understanding(
    db: AsyncSession, agent: Agent, signal: Signal
) -> None:
    """Update agent engagement metrics based on the signal."""
    # Update last contact timestamp for any contact-related signal
    contact_signals = {
        SignalType.VOICE_CALL_OUTCOME,
        SignalType.WHATSAPP_AGENT_REPLIED,
        SignalType.WHATSAPP_MESSAGE_SENT,
        SignalType.ADM_AGENT_CALL_LOGGED,
        SignalType.ADM_AGENT_VISIT_LOGGED,
    }
    if signal.signal_type in contact_signals:
        agent.last_contact_at = signal.timestamp

    # Update last positive signal timestamp
    if is_positive_signal(signal.signal_type, signal.payload):
        agent.last_positive_signal_at = signal.timestamp

    # Update sales counters for POLICY_SOLD
    if signal.signal_type == SignalType.POLICY_SOLD:
        agent.total_policies_sold = (agent.total_policies_sold or 0) + 1
        agent.policies_sold_last_12m = (agent.policies_sold_last_12m or 0) + 1


async def _check_lifecycle_transition(
    db: AsyncSession, agent: Agent, signal: Signal
) -> None:
    """Check if this signal triggers a lifecycle state transition."""
    new_state = compute_transition(
        current_state=agent.lifecycle_state,
        signal_type=signal.signal_type,
        payload=signal.payload,
        agent=agent,
    )

    if new_state is None:
        return

    previous_state = agent.lifecycle_state
    agent.lifecycle_state = new_state
    agent.state_since = datetime.now(timezone.utc)

    # Clear dormancy reason when leaving dormant state
    if previous_state == "dormant" and new_state != "dormant":
        agent.dormancy_reason = None

    logger.info(
        "Agent %s lifecycle: %s → %s (trigger: %s signal %s)",
        agent.id, previous_state, new_state, signal.signal_type, signal.id,
    )

    # Emit lifecycle_state_changed signal (append to signal stream)
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
            "reason": f"Triggered by {signal.signal_type}",
        },
        metadata_={},
        processed=True,  # System signals are pre-processed
        processed_at=datetime.now(timezone.utc),
    )
    db.add(lifecycle_signal)

    # Publish event on internal bus
    await event_bus.publish(
        LifecycleStateChanged(
            tenant_id=agent.tenant_id,
            agent_id=agent.id,
            previous_state=previous_state,
            new_state=new_state,
        )
    )


async def _check_adm_alert_triggers(
    db: AsyncSession, agent: Agent, signal: Signal,
    pre_transition_state: str | None = None,
) -> None:
    """Auto-create ADM alerts from specific signal patterns.

    Uses pre_transition_state to check dormancy, since lifecycle may have
    already changed by the time this runs.

    Triggers:
    - WHATSAPP_AGENT_REPLIED while DORMANT → REENGAGEMENT_SIGNAL (HIGH)
    - VOICE_CALL_OUTCOME ANSWERED while DORMANT → REENGAGEMENT_SIGNAL (HIGH)
    - WHATSAPP_TRAINING_INTERACTION QUIZ_COMPLETED → TRAINING_COMPLETED (LOW)
    - CONSENT_CHANGED revoked → OPTED_OUT (CRITICAL)
    - LICENSE_STATUS_CHANGED expiry < 30 days → LICENSE_EXPIRING (HIGH)
    """
    if not agent.assigned_adm_id:
        return

    adm_id = agent.assigned_adm_id
    tenant_id = agent.tenant_id
    state = pre_transition_state or agent.lifecycle_state

    # Dormant agent replied via WhatsApp
    if (
        signal.signal_type == SignalType.WHATSAPP_AGENT_REPLIED
        and state == "dormant"
    ):
        await adm_alerts.create_alert(
            db, tenant_id, adm_id, agent.id,
            alert_type="REENGAGEMENT_SIGNAL",
            urgency="HIGH",
            message=f"{agent.full_name} replied on WhatsApp — dormant agent showing interest",
        )
        return

    # Dormant agent answered voice call
    if (
        signal.signal_type == SignalType.VOICE_CALL_OUTCOME
        and state == "dormant"
        and signal.payload.get("outcome") == "answered"
    ):
        await adm_alerts.create_alert(
            db, tenant_id, adm_id, agent.id,
            alert_type="REENGAGEMENT_SIGNAL",
            urgency="HIGH",
            message=f"{agent.full_name} answered a call — dormant agent re-engaging",
        )
        return

    # Training quiz completed
    if (
        signal.signal_type == SignalType.WHATSAPP_TRAINING_INTERACTION
        and signal.payload.get("interaction_type") == "QUIZ_COMPLETED"
    ):
        score = signal.payload.get("quiz_score", 0)
        await adm_alerts.create_alert(
            db, tenant_id, adm_id, agent.id,
            alert_type="TRAINING_COMPLETED",
            urgency="LOW",
            message=f"{agent.full_name} completed training quiz (Score: {score:.0f}%)",
        )
        return

    # Consent revoked
    if (
        signal.signal_type == SignalType.CONSENT_CHANGED
        and signal.payload.get("new_status") == "revoked"
    ):
        consent_type = signal.payload.get("consent_type", "communication")
        await adm_alerts.create_alert(
            db, tenant_id, adm_id, agent.id,
            alert_type="OPTED_OUT",
            urgency="CRITICAL",
            message=f"{agent.full_name} revoked {consent_type} consent",
        )
        return

    # License expiring soon
    if signal.signal_type == SignalType.LICENSE_STATUS_CHANGED:
        expiry_date_str = signal.payload.get("expiry_date")
        if expiry_date_str:
            try:
                expiry = datetime.fromisoformat(expiry_date_str)
                days_left = (expiry - datetime.now(timezone.utc)).days
                if 0 < days_left <= 30:
                    await adm_alerts.create_alert(
                        db, tenant_id, adm_id, agent.id,
                        alert_type="LICENSE_EXPIRING",
                        urgency="HIGH",
                        message=f"{agent.full_name}'s license expires in {days_left} days",
                    )
            except (ValueError, TypeError):
                pass


async def _trigger_immediate_evaluation(
    db: AsyncSession, agent: Agent, signal: Signal,
    pre_transition_state: str | None = None,
) -> None:
    """Trigger immediate decision evaluation for high-priority signals.

    Signals that warrant immediate evaluation:
    - POLICY_SOLD → celebrate first sale
    - CONSENT_CHANGED revoked → pause outreach
    - WHATSAPP_AGENT_REPLIED while dormant → reactivation opportunity
    - VOICE_CALL_OUTCOME answered while dormant → reactivation opportunity
    """
    from modules.decision import engine as decision_engine

    state = pre_transition_state or agent.lifecycle_state
    should_evaluate = False

    if signal.signal_type == SignalType.POLICY_SOLD:
        should_evaluate = True

    elif (
        signal.signal_type == SignalType.CONSENT_CHANGED
        and signal.payload.get("new_status") == "revoked"
    ):
        should_evaluate = True

    elif signal.signal_type == SignalType.WHATSAPP_AGENT_REPLIED and state == "dormant":
        should_evaluate = True

    elif (
        signal.signal_type == SignalType.VOICE_CALL_OUTCOME
        and state == "dormant"
        and signal.payload.get("outcome") == "answered"
    ):
        should_evaluate = True

    if should_evaluate:
        try:
            await decision_engine.evaluate_agent(db, agent.id, agent.tenant_id)
            logger.info(
                "Immediate decision evaluation triggered for agent %s (signal: %s)",
                agent.id, signal.signal_type,
            )
        except Exception:
            logger.exception(
                "Failed immediate decision evaluation for agent %s", agent.id,
            )
