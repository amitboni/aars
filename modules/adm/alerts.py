"""modules/adm/alerts.py — ADM alert creation and management.

Per spec section 3.4.3: time-sensitive notifications that shouldn't wait for morning briefing.
Alert types: REENGAGEMENT_SIGNAL, TRAINING_COMPLETED, OPTED_OUT, LICENSE_EXPIRING, ESCALATION.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import SignalType
from modules.adm.models import ADMAlert
from modules.signal.schemas import SignalEmit
from modules.signal import service as signal_service

logger = logging.getLogger(__name__)


async def create_alert(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    adm_id: uuid.UUID,
    agent_id: uuid.UUID,
    alert_type: str,
    urgency: str,
    message: str,
) -> ADMAlert:
    """Create an ADM alert and emit ADM_NUDGE_RECEIVED signal."""
    alert = ADMAlert(
        tenant_id=tenant_id,
        adm_id=adm_id,
        agent_id=agent_id,
        alert_type=alert_type,
        urgency=urgency,
        message=message,
    )
    db.add(alert)
    await db.flush()

    # Emit ADM_NUDGE_RECEIVED signal
    signal_data = SignalEmit(
        signal_type=SignalType.ADM_NUDGE_RECEIVED,
        source="system",
        agent_id=agent_id,
        adm_id=adm_id,
        channel="whatsapp_adm",
        payload={
            "nudge_type": "AGENT_ALERT",
            "alert_type": alert_type,
            "urgency": urgency,
            "content_summary": message,
            "alert_id": str(alert.id),
        },
        idempotency_key=f"adm_alert:{alert.id}",
    )
    await signal_service.emit_signal(db, tenant_id, signal_data)

    logger.info(
        "ADM alert created: type=%s urgency=%s adm=%s agent=%s",
        alert_type, urgency, adm_id, agent_id,
    )
    return alert


async def mark_alert_read(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    alert_id: uuid.UUID,
) -> ADMAlert | None:
    """Mark an alert as read."""
    result = await db.execute(
        select(ADMAlert).where(
            ADMAlert.id == alert_id,
            ADMAlert.tenant_id == tenant_id,
        )
    )
    alert = result.scalar_one_or_none()
    if alert and not alert.read_at:
        alert.read_at = datetime.now(timezone.utc)
        await db.flush()
    return alert


async def mark_alert_acted_on(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    alert_id: uuid.UUID,
) -> ADMAlert | None:
    """Mark an alert as acted upon."""
    result = await db.execute(
        select(ADMAlert).where(
            ADMAlert.id == alert_id,
            ADMAlert.tenant_id == tenant_id,
        )
    )
    alert = result.scalar_one_or_none()
    if alert and not alert.acted_on_at:
        now = datetime.now(timezone.utc)
        alert.acted_on_at = now
        if not alert.read_at:
            alert.read_at = now
        await db.flush()

        # Emit ADM_NUDGE_ACTED_ON signal
        time_to_act = None
        if alert.created_at:
            time_to_act = int((now - alert.created_at).total_seconds() / 60)
        signal_data = SignalEmit(
            signal_type=SignalType.ADM_NUDGE_ACTED_ON,
            source="system",
            agent_id=alert.agent_id,
            adm_id=alert.adm_id,
            channel="whatsapp_adm",
            payload={
                "nudge_id": str(alert.id),
                "action_taken": "ACKNOWLEDGED",
                "time_to_action_minutes": time_to_act,
            },
            idempotency_key=f"adm_acted:{alert.id}",
        )
        await signal_service.emit_signal(db, tenant_id, signal_data)

    return alert


async def list_alerts(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    adm_id: uuid.UUID,
    unread_only: bool = False,
    urgency: str | None = None,
    limit: int = 50,
    cursor: uuid.UUID | None = None,
) -> tuple[list[ADMAlert], uuid.UUID | None]:
    """List alerts for an ADM with filters and cursor-based pagination."""
    query = (
        select(ADMAlert)
        .where(
            ADMAlert.tenant_id == tenant_id,
            ADMAlert.adm_id == adm_id,
        )
        .order_by(ADMAlert.created_at.desc(), ADMAlert.id)
        .limit(limit + 1)
    )
    if unread_only:
        query = query.where(ADMAlert.read_at.is_(None))
    if urgency:
        query = query.where(ADMAlert.urgency == urgency)
    if cursor:
        cursor_alert = await db.get(ADMAlert, cursor)
        if cursor_alert:
            query = query.where(
                (ADMAlert.created_at < cursor_alert.created_at)
                | (
                    (ADMAlert.created_at == cursor_alert.created_at)
                    & (ADMAlert.id > cursor_alert.id)
                )
            )

    result = await db.execute(query)
    alerts = list(result.scalars().all())

    next_cursor = None
    if len(alerts) > limit:
        alerts = alerts[:limit]
        next_cursor = alerts[-1].id

    return alerts, next_cursor
