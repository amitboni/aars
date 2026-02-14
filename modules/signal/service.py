"""modules/signal/service.py — Signal emit and query operations."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConflictError
from modules.signal.models import Signal
from modules.signal.schemas import SignalEmit

logger = logging.getLogger(__name__)


async def emit_signal(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: SignalEmit,
) -> tuple[Signal, bool]:
    """Emit a new signal. Returns (signal, created).

    If idempotency_key is provided and already exists for this tenant,
    returns the existing signal with created=False.
    """
    # Idempotency check
    if data.idempotency_key:
        existing = await db.execute(
            select(Signal).where(
                Signal.tenant_id == tenant_id,
                Signal.idempotency_key == data.idempotency_key,
            )
        )
        found = existing.scalar_one_or_none()
        if found:
            return found, False

    signal = Signal(
        tenant_id=tenant_id,
        signal_type=data.signal_type,
        source=data.source,
        agent_id=data.agent_id,
        adm_id=data.adm_id,
        timestamp=data.timestamp or datetime.now(timezone.utc),
        channel=data.channel,
        conversation_id=data.conversation_id,
        payload=data.payload,
        metadata_=data.metadata,
        idempotency_key=data.idempotency_key,
        processed=False,
    )
    db.add(signal)
    await db.flush()
    return signal, True


async def get_signal(db: AsyncSession, signal_id: uuid.UUID, tenant_id: uuid.UUID) -> Signal | None:
    result = await db.execute(
        select(Signal).where(
            Signal.id == signal_id,
            Signal.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def list_signals(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 50,
    cursor: uuid.UUID | None = None,
    signal_type: str | None = None,
    agent_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[Signal], uuid.UUID | None]:
    """List signals with cursor-based pagination and filters."""
    query = (
        select(Signal)
        .where(Signal.tenant_id == tenant_id)
        .order_by(Signal.timestamp.desc(), Signal.id)
        .limit(limit + 1)
    )
    if signal_type:
        query = query.where(Signal.signal_type == signal_type)
    if agent_id:
        query = query.where(Signal.agent_id == agent_id)
    if date_from:
        query = query.where(Signal.timestamp >= date_from)
    if date_to:
        query = query.where(Signal.timestamp <= date_to)

    if cursor:
        cursor_signal = await db.get(Signal, cursor)
        if cursor_signal:
            query = query.where(
                (Signal.timestamp < cursor_signal.timestamp)
                | (
                    (Signal.timestamp == cursor_signal.timestamp)
                    & (Signal.id > cursor_signal.id)
                )
            )

    result = await db.execute(query)
    signals = list(result.scalars().all())

    next_cursor = None
    if len(signals) > limit:
        signals = signals[:limit]
        next_cursor = signals[-1].id

    return signals, next_cursor


async def get_unprocessed_signals(
    db: AsyncSession,
    limit: int = 100,
) -> list[Signal]:
    """Get signals that have not been processed yet (slow path)."""
    result = await db.execute(
        select(Signal)
        .where(Signal.processed.is_(False))
        .order_by(Signal.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def mark_processed(db: AsyncSession, signal: Signal) -> None:
    """Mark a signal as processed."""
    signal.processed = True
    signal.processed_at = datetime.now(timezone.utc)
    await db.flush()
