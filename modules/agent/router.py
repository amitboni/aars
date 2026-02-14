"""modules/agent/router.py — Agent API endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_role
from modules.agent.schemas import AgentCreate, AgentUpdate, AgentResponse
from modules.agent import service

router = APIRouter(prefix="/api/v1", tags=["agents"])


@router.post(
    "/agents",
    response_model=AgentResponse,
    status_code=201,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def create_agent(
    data: AgentCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    agent = await service.create_agent(db, user["tenant_id"], data)
    return AgentResponse.model_validate(agent)


@router.post(
    "/agents/import",
    status_code=201,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def bulk_import_agents(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Bulk CSV import of agents (spec 4.13: POST /api/v1/agents/import).

    Processes agent master CSV through the PAS adapter and computes
    initial lifecycle states per spec 3.9:
    - Has active policies in last 90 days → ACTIVE
    - Has policies but none in last 90 days → AT_RISK or DORMANT
    - Licensed but never sold → LICENSED
    - License expired → LAPSED
    - Default → ONBOARDED
    """
    from modules.integration import service as int_service
    from modules.integration.schemas import IntegrationJobResponse

    tenant_id = user["tenant_id"] if isinstance(user["tenant_id"], uuid.UUID) else uuid.UUID(str(user["tenant_id"]))
    user_id = user["user_id"] if isinstance(user["user_id"], uuid.UUID) else uuid.UUID(str(user["user_id"]))

    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
    if ext not in ("csv", "xlsx", "xls"):
        raise HTTPException(400, "File must be CSV (.csv) or Excel (.xlsx/.xls)")

    content = await file.read()
    if not content:
        raise HTTPException(400, "Uploaded file is empty")

    job = await int_service.process_upload(
        db=db,
        tenant_id=tenant_id,
        content=content,
        file_name=file.filename or "import.csv",
        source_system="pas",
        user_id=user_id,
    )

    return IntegrationJobResponse.model_validate(job)


@router.get(
    "/agents",
    dependencies=[Depends(require_role("super_admin", "tenant_admin", "regional_manager", "adm"))],
)
async def list_agents(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    cursor: uuid.UUID | None = Query(None),
    lifecycle_state: str | None = Query(None),
    adm_id: uuid.UUID | None = Query(None),
    region_node_id: uuid.UUID | None = Query(None),
):
    agents, next_cursor = await service.list_agents(
        db, user["tenant_id"], limit, cursor,
        lifecycle_state=lifecycle_state,
        assigned_adm_id=adm_id,
        region_node_id=region_node_id,
    )
    return {
        "data": [AgentResponse.model_validate(a) for a in agents],
        "next_cursor": str(next_cursor) if next_cursor else None,
        "has_more": next_cursor is not None,
    }


@router.get(
    "/agents/{agent_id}",
    response_model=AgentResponse,
    dependencies=[Depends(require_role("super_admin", "tenant_admin", "regional_manager", "adm"))],
)
async def get_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    agent = await service.get_agent(db, agent_id, user["tenant_id"])
    return AgentResponse.model_validate(agent)


@router.put(
    "/agents/{agent_id}",
    response_model=AgentResponse,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def update_agent(
    agent_id: uuid.UUID,
    data: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    agent = await service.update_agent(db, agent_id, user["tenant_id"], data)
    return AgentResponse.model_validate(agent)
