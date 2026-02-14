"""modules/decision/router.py — Decision Engine API routes.

3 endpoints under /api/v1/decisions/:
- GET  /decisions                     — list decision logs
- GET  /decisions/{id}                — decision log detail
- POST /decisions/evaluate/{agent_id} — trigger immediate evaluation
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_role
from core.enums import UserRole
from modules.decision import engine as decision_engine
from modules.decision.models import DecisionLog
from modules.decision.schemas import DecisionLogResponse

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])


def _to_uuid(value) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


@router.get("")
async def list_decisions(
    agent_id: uuid.UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    cursor: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(UserRole.ADM, UserRole.TENANT_ADMIN)),
):
    """List decision logs with optional agent filter and cursor pagination."""
    tenant_id = _to_uuid(user["tenant_id"])
    query = (
        select(DecisionLog)
        .where(DecisionLog.tenant_id == tenant_id)
        .order_by(DecisionLog.created_at.desc(), DecisionLog.id)
        .limit(limit + 1)
    )
    if agent_id:
        query = query.where(DecisionLog.agent_id == agent_id)
    if cursor:
        cursor_log = await db.get(DecisionLog, cursor)
        if cursor_log:
            query = query.where(
                (DecisionLog.created_at < cursor_log.created_at)
                | (
                    (DecisionLog.created_at == cursor_log.created_at)
                    & (DecisionLog.id > cursor_log.id)
                )
            )

    result = await db.execute(query)
    logs = list(result.scalars().all())

    next_cursor = None
    if len(logs) > limit:
        logs = logs[:limit]
        next_cursor = logs[-1].id

    return {
        "data": [DecisionLogResponse.model_validate(l).model_dump(mode="json") for l in logs],
        "next_cursor": str(next_cursor) if next_cursor else None,
        "has_more": next_cursor is not None,
    }


@router.get("/{decision_id}", response_model=DecisionLogResponse)
async def get_decision(
    decision_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(UserRole.ADM, UserRole.TENANT_ADMIN)),
):
    """Get a single decision log by ID."""
    tenant_id = _to_uuid(user["tenant_id"])
    result = await db.execute(
        select(DecisionLog).where(
            DecisionLog.id == decision_id,
            DecisionLog.tenant_id == tenant_id,
        )
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(404, "Decision log not found")
    return log


@router.post("/evaluate/{agent_id}", response_model=DecisionLogResponse)
async def evaluate_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(UserRole.ADM, UserRole.TENANT_ADMIN)),
):
    """Trigger immediate decision evaluation for a specific agent."""
    tenant_id = _to_uuid(user["tenant_id"])
    try:
        log = await decision_engine.evaluate_agent(db, agent_id, tenant_id)
        await db.commit()
        return log
    except ValueError as e:
        raise HTTPException(404, str(e))
