"""modules/agent/lifecycle.py — Agent lifecycle state machine and positive signal classification."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from core.enums import AgentLifecycleState, SignalType

logger = logging.getLogger(__name__)

# ─── Positive Signal Classification ─────────────────────────────────────────

ALWAYS_POSITIVE: set[str] = {
    SignalType.POLICY_SOLD,
    SignalType.WHATSAPP_AGENT_REPLIED,
    SignalType.TRAINING_COMPLETED_EXTERNAL,
    SignalType.ADM_AGENT_VISIT_LOGGED,
}


def is_positive_signal(signal_type: str, payload: dict) -> bool:
    """Evaluate whether a specific signal instance is a positive engagement signal."""
    if signal_type in ALWAYS_POSITIVE:
        return True
    if signal_type == SignalType.VOICE_CALL_OUTCOME:
        return payload.get("outcome") in ("answered", "completed")
    if signal_type == SignalType.WHATSAPP_TRAINING_INTERACTION:
        return (
            (payload.get("completion_percentage", 0) or 0) > 50
            or payload.get("interaction_type") == "QUIZ_COMPLETED"
        )
    if signal_type == SignalType.ADM_AGENT_CALL_LOGGED:
        return payload.get("outcome") in ("CONNECTED", "DETAILED_DISCUSSION")
    return False


# ─── Lifecycle FSM Transition Table ──────────────────────────────────────────
# Maps (current_state, signal_type) → new_state
# The check functions receive (agent, signal_type, payload) and return new state or None.

def _check_onboarded(signal_type: str, payload: dict, agent) -> str | None:
    """Transitions from ONBOARDED."""
    if signal_type == SignalType.LICENSE_STATUS_CHANGED:
        if payload.get("new_status") == "ACTIVE":
            return AgentLifecycleState.LICENSED
    return None


def _check_licensed(signal_type: str, payload: dict, agent) -> str | None:
    """Transitions from LICENSED."""
    if signal_type == SignalType.POLICY_SOLD:
        return AgentLifecycleState.FIRST_SALE
    return None


def _check_first_sale(signal_type: str, payload: dict, agent) -> str | None:
    """Transitions from FIRST_SALE."""
    if signal_type == SignalType.POLICY_SOLD:
        # If agent has crossed tenant's active threshold, promote to ACTIVE
        # For now, use default: 2+ total policies means active
        if (agent.total_policies_sold or 0) + 1 >= 2:
            return AgentLifecycleState.ACTIVE
    return None


def _check_active(signal_type: str, payload: dict, agent) -> str | None:
    """Transitions from ACTIVE."""
    # ACTIVE → PRODUCTIVE: requires sustained performance (handled by periodic check, not single signal)
    # ACTIVE → AT_RISK: engagement score drop (handled by periodic check)
    return None


def _check_productive(signal_type: str, payload: dict, agent) -> str | None:
    """Transitions from PRODUCTIVE."""
    # PRODUCTIVE → AT_RISK: production drop (handled by periodic check)
    return None


def _check_at_risk(signal_type: str, payload: dict, agent) -> str | None:
    """Transitions from AT_RISK."""
    if signal_type == SignalType.POLICY_SOLD:
        return AgentLifecycleState.ACTIVE
    if is_positive_signal(signal_type, payload):
        # Strong re-engagement: check engagement score threshold
        if (agent.engagement_score or 0) > 60:
            return AgentLifecycleState.ACTIVE
    return None


def _check_dormant(signal_type: str, payload: dict, agent) -> str | None:
    """Transitions from DORMANT."""
    if signal_type == SignalType.POLICY_SOLD:
        return AgentLifecycleState.ACTIVE
    if is_positive_signal(signal_type, payload):
        # Re-engagement without sale → back to LICENSED
        return AgentLifecycleState.LICENSED
    return None


def _check_lapsed(signal_type: str, payload: dict, agent) -> str | None:
    """Transitions from LAPSED."""
    if signal_type == SignalType.LICENSE_STATUS_CHANGED:
        if payload.get("new_status") == "ACTIVE":
            return AgentLifecycleState.LICENSED
    return None


def _check_terminated(signal_type: str, payload: dict, agent) -> str | None:
    """TERMINATED is a final state. No automatic transitions out."""
    return None


# Global transitions that apply from ANY state
def _check_global(signal_type: str, payload: dict, agent) -> str | None:
    """Transitions that can happen from any state."""
    if signal_type == SignalType.LICENSE_STATUS_CHANGED:
        if payload.get("new_status") == "EXPIRED":
            return AgentLifecycleState.LAPSED
    return None


_STATE_HANDLERS: dict[str, callable] = {
    AgentLifecycleState.ONBOARDED: _check_onboarded,
    AgentLifecycleState.LICENSED: _check_licensed,
    AgentLifecycleState.FIRST_SALE: _check_first_sale,
    AgentLifecycleState.ACTIVE: _check_active,
    AgentLifecycleState.PRODUCTIVE: _check_productive,
    AgentLifecycleState.AT_RISK: _check_at_risk,
    AgentLifecycleState.DORMANT: _check_dormant,
    AgentLifecycleState.LAPSED: _check_lapsed,
    AgentLifecycleState.TERMINATED: _check_terminated,
}


def compute_transition(
    current_state: str,
    signal_type: str,
    payload: dict,
    agent,
) -> str | None:
    """Determine if a signal triggers a lifecycle state transition.

    Returns the new state or None if no transition should occur.
    """
    # Check global transitions first (license expiry overrides everything)
    new_state = _check_global(signal_type, payload, agent)
    if new_state and new_state != current_state:
        return new_state

    # Check state-specific handler
    handler = _STATE_HANDLERS.get(current_state)
    if handler:
        new_state = handler(signal_type, payload, agent)
        if new_state and new_state != current_state:
            return new_state

    return None
