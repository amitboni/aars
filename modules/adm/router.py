"""modules/adm/router.py — ADM Experience API routes.

9 endpoints under /api/v1/adm/:
- GET  /briefing              — morning briefing
- GET  /briefing/weekly       — weekly summary
- GET  /agents                — list ADM's agents
- GET  /agents/{agent_id}/detail — agent detail for ADM
- POST /actions               — log ADM action
- GET  /alerts                — list alerts
- POST /alerts/{alert_id}/read   — mark alert read
- POST /alerts/{alert_id}/acted  — mark alert acted on
- GET  /effectiveness         — ADM effectiveness metrics
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_role
from core.enums import UserRole
from modules.adm import alerts as alerts_service
from modules.adm import briefing as briefing_service
from modules.adm import service as adm_service
from modules.adm.action_logger import log_action
from modules.adm.schemas import (
    ADMActionCreate,
    ADMActionResponse,
    ADMEffectivenessResponse,
    AgentDetailResponse,
    AlertResponse,
    MorningBriefingResponse,
    WeeklySummaryResponse,
)

router = APIRouter(prefix="/api/v1/adm", tags=["adm"])


def _to_uuid(value) -> uuid.UUID:
    """Convert a value to UUID, handling both str and UUID inputs."""
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


@router.get("/briefing", response_model=MorningBriefingResponse)
async def get_morning_briefing(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(UserRole.ADM, UserRole.TENANT_ADMIN)),
):
    """Generate and return morning briefing for the authenticated ADM."""
    tenant_id = _to_uuid(user["tenant_id"])
    adm_id = _to_uuid(user["user_id"])
    return await briefing_service.generate_morning_briefing(db, tenant_id, adm_id)


@router.get("/briefing/weekly", response_model=WeeklySummaryResponse)
async def get_weekly_summary(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(UserRole.ADM, UserRole.TENANT_ADMIN)),
):
    """Generate and return weekly summary for the authenticated ADM."""
    tenant_id = _to_uuid(user["tenant_id"])
    adm_id = _to_uuid(user["user_id"])
    return await briefing_service.generate_weekly_summary(db, tenant_id, adm_id)


@router.get("/agents")
async def list_agents(
    lifecycle_state: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    cursor: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(UserRole.ADM, UserRole.TENANT_ADMIN)),
):
    """List agents assigned to the authenticated ADM."""
    tenant_id = _to_uuid(user["tenant_id"])
    adm_id = _to_uuid(user["user_id"])
    agents, next_cursor = await adm_service.list_adm_agents(
        db, tenant_id, adm_id,
        lifecycle_state=lifecycle_state,
        limit=limit,
        cursor=cursor,
    )
    return {
        "data": [
            {
                "id": str(a.id),
                "full_name": a.full_name,
                "lifecycle_state": a.lifecycle_state,
                "phone": a.phone,
                "last_contact_at": a.last_contact_at.isoformat() if a.last_contact_at else None,
                "engagement_score": a.engagement_score,
            }
            for a in agents
        ],
        "next_cursor": str(next_cursor) if next_cursor else None,
        "has_more": next_cursor is not None,
    }


@router.get("/agents/{agent_id}/detail", response_model=AgentDetailResponse)
async def get_agent_detail(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(UserRole.ADM, UserRole.TENANT_ADMIN)),
):
    """Get detailed agent view for the authenticated ADM."""
    tenant_id = _to_uuid(user["tenant_id"])
    adm_id = _to_uuid(user["user_id"])
    detail = await adm_service.get_agent_detail_for_adm(
        db, tenant_id, adm_id, agent_id
    )
    if not detail:
        raise HTTPException(404, "Agent not found or not assigned to you")
    return detail


@router.post("/actions", response_model=ADMActionResponse)
async def create_action(
    body: ADMActionCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(UserRole.ADM, UserRole.TENANT_ADMIN)),
):
    """Log an ADM action (call, visit, training, etc.)."""
    tenant_id = _to_uuid(user["tenant_id"])
    adm_id = _to_uuid(user["user_id"])
    action = await log_action(
        db,
        tenant_id=tenant_id,
        adm_id=adm_id,
        agent_id=body.agent_id,
        action_type=body.action_type,
        notes=body.notes,
        outcome=body.outcome,
        source=body.source,
    )
    return action


@router.get("/alerts")
async def list_alerts(
    unread_only: bool = Query(False),
    urgency: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    cursor: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(UserRole.ADM, UserRole.TENANT_ADMIN)),
):
    """List alerts for the authenticated ADM."""
    tenant_id = _to_uuid(user["tenant_id"])
    adm_id = _to_uuid(user["user_id"])
    alerts, next_cursor = await alerts_service.list_alerts(
        db, tenant_id, adm_id,
        unread_only=unread_only,
        urgency=urgency,
        limit=limit,
        cursor=cursor,
    )
    return {
        "data": [AlertResponse.model_validate(a).model_dump(mode="json") for a in alerts],
        "next_cursor": str(next_cursor) if next_cursor else None,
        "has_more": next_cursor is not None,
    }


@router.post("/alerts/{alert_id}/read", response_model=AlertResponse)
async def mark_alert_read(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(UserRole.ADM, UserRole.TENANT_ADMIN)),
):
    """Mark an alert as read."""
    tenant_id = _to_uuid(user["tenant_id"])
    alert = await alerts_service.mark_alert_read(db, tenant_id, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    return alert


@router.post("/alerts/{alert_id}/acted", response_model=AlertResponse)
async def mark_alert_acted(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(UserRole.ADM, UserRole.TENANT_ADMIN)),
):
    """Mark an alert as acted upon."""
    tenant_id = _to_uuid(user["tenant_id"])
    alert = await alerts_service.mark_alert_acted_on(db, tenant_id, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    return alert


@router.get("/effectiveness", response_model=ADMEffectivenessResponse)
async def get_effectiveness(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(UserRole.ADM, UserRole.TENANT_ADMIN)),
):
    """Get ADM effectiveness metrics and classification."""
    tenant_id = _to_uuid(user["tenant_id"])
    adm_id = _to_uuid(user["user_id"])
    return await adm_service.compute_adm_effectiveness(db, tenant_id, adm_id)
