"""modules/signal/router.py — Signal API endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_role
from core.events import SignalReceived, event_bus
from modules.signal.schemas import SignalEmit, SignalResponse
from modules.signal import service
from modules.signal.processor import process_signal

router = APIRouter(prefix="/api/v1", tags=["signals"])


@router.post(
    "/signals",
    status_code=201,
    dependencies=[Depends(require_role("super_admin", "tenant_admin", "adm", "support_engineer"))],
)
async def emit_signal(
    data: SignalEmit,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    signal, created = await service.emit_signal(db, user["tenant_id"], data)

    if created:
        # FAST PATH: process immediately in-process
        await process_signal(db, signal)

        # Publish event on internal bus
        await event_bus.publish(
            SignalReceived(
                tenant_id=signal.tenant_id,
                signal_id=signal.id,
                signal_type=signal.signal_type,
                agent_id=signal.agent_id,
            )
        )

    return {
        "signal": SignalResponse.model_validate(signal),
        "created": created,
    }


@router.get(
    "/signals",
    dependencies=[Depends(require_role("super_admin", "tenant_admin", "analyst"))],
)
async def list_signals(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    cursor: uuid.UUID | None = Query(None),
    signal_type: str | None = Query(None),
    agent_id: uuid.UUID | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
):
    signals, next_cursor = await service.list_signals(
        db, user["tenant_id"], limit, cursor,
        signal_type=signal_type,
        agent_id=agent_id,
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "data": [SignalResponse.model_validate(s) for s in signals],
        "next_cursor": str(next_cursor) if next_cursor else None,
        "has_more": next_cursor is not None,
    }


@router.get(
    "/agents/{agent_id}/signals",
    dependencies=[Depends(require_role("super_admin", "tenant_admin", "regional_manager", "adm"))],
)
async def list_agent_signals(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    cursor: uuid.UUID | None = Query(None),
    signal_type: str | None = Query(None),
):
    signals, next_cursor = await service.list_signals(
        db, user["tenant_id"], limit, cursor,
        signal_type=signal_type,
        agent_id=agent_id,
    )
    return {
        "data": [SignalResponse.model_validate(s) for s in signals],
        "next_cursor": str(next_cursor) if next_cursor else None,
        "has_more": next_cursor is not None,
    }
