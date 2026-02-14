"""modules/adm/action_logger.py — ADM action logging.

Per spec section 3.4.5: effortless action capture.
Logs ADM actions and emits corresponding signals that feed back
into agent understanding and lifecycle engine.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import SignalType
from modules.adm.models import ADMAction
from modules.signal.schemas import SignalEmit
from modules.signal import service as signal_service

logger = logging.getLogger(__name__)


async def log_action(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    adm_id: uuid.UUID,
    agent_id: uuid.UUID,
    action_type: str,
    notes: str | None = None,
    outcome: dict | None = None,
    source: str = "MANUAL",
    nudge_reference_id: uuid.UUID | None = None,
) -> ADMAction:
    """Log an ADM action and emit the corresponding signal.

    Args:
        db: Database session.
        tenant_id: Tenant UUID.
        adm_id: ADM user UUID.
        agent_id: Agent UUID the action is about.
        action_type: CALLED_AGENT, VISITED_AGENT, SENT_TRAINING, ESCALATED, ACKNOWLEDGED, FORWARDED_CONTENT.
        notes: Optional notes from ADM.
        outcome: Optional outcome dict {result: "positive"|"okay"|"not_great"|"skip"}.
        source: NUDGE_REPLY, QUICK_LOG, VOICE_NOTE_LOG, MANUAL.
        nudge_reference_id: UUID of the nudge/alert that triggered this action.
    """
    action = ADMAction(
        tenant_id=tenant_id,
        adm_id=adm_id,
        agent_id=agent_id,
        action_type=action_type,
        notes=notes,
        outcome=outcome,
        source=source,
        nudge_reference_id=nudge_reference_id,
    )
    db.add(action)
    await db.flush()

    # Emit the appropriate signal
    signal_type, signal_payload = _build_signal(action_type, notes, outcome)
    if signal_type:
        signal_data = SignalEmit(
            signal_type=signal_type,
            source="adm_report",
            agent_id=agent_id,
            adm_id=adm_id,
            channel="adm_call" if action_type == "CALLED_AGENT" else "adm_visit",
            payload=signal_payload,
            idempotency_key=f"adm_action:{action.id}",
        )
        await signal_service.emit_signal(db, tenant_id, signal_data)

    logger.info(
        "ADM action logged: type=%s adm=%s agent=%s source=%s",
        action_type, adm_id, agent_id, source,
    )
    return action


def _build_signal(
    action_type: str,
    notes: str | None,
    outcome: dict | None,
) -> tuple[str | None, dict]:
    """Build signal type and payload for an ADM action."""
    result = (outcome or {}).get("result", "okay")

    if action_type == "CALLED_AGENT":
        return SignalType.ADM_AGENT_CALL_LOGGED, {
            "outcome": _map_outcome(result),
            "notes": notes or "",
        }

    if action_type == "VISITED_AGENT":
        return SignalType.ADM_AGENT_VISIT_LOGGED, {
            "visit_purpose": "COACHING",
            "outcome": notes or "",
        }

    # Other action types don't emit specific signals
    # but the action record itself is stored
    return None, {}


def _map_outcome(result: str) -> str:
    """Map simplified outcome to signal payload outcome."""
    mapping = {
        "positive": "DETAILED_DISCUSSION",
        "okay": "BRIEF_CHAT",
        "not_great": "CONNECTED",
        "skip": "NOT_ANSWERED",
    }
    return mapping.get(result, "CONNECTED")
