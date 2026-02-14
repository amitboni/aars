"""modules/playbook/router.py — Playbook API endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_role
from modules.playbook import service
from modules.playbook.schemas import (
    PlaybookCreate,
    PlaybookResponse,
    PlaybookRunResponse,
    PlaybookSummaryResponse,
    PlaybookTrigger,
    PlaybookUpdate,
)

router = APIRouter(prefix="/api/v1", tags=["playbooks"])


# ─── Playbook CRUD (collection routes first) ─────────────────────────────────

@router.post(
    "/playbooks",
    response_model=PlaybookResponse,
    status_code=201,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def create_playbook(
    data: PlaybookCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    playbook = await service.create_playbook(db, user["tenant_id"], data)
    return PlaybookResponse.model_validate(playbook)


@router.get(
    "/playbooks",
    dependencies=[Depends(require_role("super_admin", "tenant_admin", "regional_manager"))],
)
async def list_playbooks(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    cursor: uuid.UUID | None = Query(None),
    is_active: bool | None = Query(None),
):
    playbooks, next_cursor = await service.list_playbooks(
        db, user["tenant_id"], limit, cursor, is_active=is_active
    )
    data = []
    for pb in playbooks:
        summary = PlaybookSummaryResponse.model_validate(pb)
        summary.steps_count = len(pb.steps) if pb.steps else 0
        data.append(summary)
    return {
        "data": data,
        "next_cursor": str(next_cursor) if next_cursor else None,
        "has_more": next_cursor is not None,
    }


# ─── Playbook Runs (MUST come before /playbooks/{playbook_id} to avoid route conflict) ──

@router.post(
    "/playbooks/trigger",
    response_model=PlaybookRunResponse,
    status_code=201,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def trigger_playbook(
    data: PlaybookTrigger,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    run = await service.trigger_playbook(db, user["tenant_id"], data)
    return PlaybookRunResponse.model_validate(run)


@router.get(
    "/playbooks/runs",
    dependencies=[Depends(require_role("super_admin", "tenant_admin", "regional_manager"))],
)
async def list_playbook_runs(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    cursor: uuid.UUID | None = Query(None),
    agent_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None),
):
    runs, next_cursor = await service.list_playbook_runs(
        db, user["tenant_id"], limit, cursor,
        agent_id=agent_id,
        status=status,
    )
    return {
        "data": [PlaybookRunResponse.model_validate(r) for r in runs],
        "next_cursor": str(next_cursor) if next_cursor else None,
        "has_more": next_cursor is not None,
    }


@router.get(
    "/playbooks/runs/{run_id}",
    response_model=PlaybookRunResponse,
    dependencies=[Depends(require_role("super_admin", "tenant_admin", "regional_manager"))],
)
async def get_playbook_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    run = await service.get_playbook_run(db, run_id, user["tenant_id"])
    return PlaybookRunResponse.model_validate(run)


# ─── Playbook Item routes (parameterized — MUST come after specific sub-paths) ──

@router.get(
    "/playbooks/{playbook_id}",
    response_model=PlaybookResponse,
    dependencies=[Depends(require_role("super_admin", "tenant_admin", "regional_manager"))],
)
async def get_playbook(
    playbook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    playbook = await service.get_playbook(db, playbook_id, user["tenant_id"])
    return PlaybookResponse.model_validate(playbook)


@router.put(
    "/playbooks/{playbook_id}",
    response_model=PlaybookResponse,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def update_playbook(
    playbook_id: uuid.UUID,
    data: PlaybookUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    playbook = await service.update_playbook(db, playbook_id, user["tenant_id"], data)
    return PlaybookResponse.model_validate(playbook)


@router.delete(
    "/playbooks/{playbook_id}",
    status_code=204,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def delete_playbook(
    playbook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    await service.delete_playbook(db, playbook_id, user["tenant_id"])
    return None
