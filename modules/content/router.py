"""modules/content/router.py — Message template API endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_role
from modules.content import service
from modules.content.schemas import (
    TemplateCreate,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    TemplateResponse,
    TemplateSummaryResponse,
    TemplateUpdate,
    TemplateVersionResponse,
)

router = APIRouter(prefix="/api/v1", tags=["templates"])


@router.post(
    "/templates",
    response_model=TemplateResponse,
    status_code=201,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def create_template(
    data: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    template = await service.create_template(db, user["tenant_id"], data)
    return TemplateResponse.model_validate(template)


@router.get(
    "/templates",
    dependencies=[Depends(require_role("super_admin", "tenant_admin", "regional_manager"))],
)
async def list_templates(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    cursor: uuid.UUID | None = Query(None),
    category: str | None = Query(None),
    status: str | None = Query(None),
):
    templates, next_cursor = await service.list_templates(
        db, user["tenant_id"], limit, cursor,
        category=category,
        status=status,
    )
    return {
        "data": [TemplateSummaryResponse.model_validate(t) for t in templates],
        "next_cursor": str(next_cursor) if next_cursor else None,
        "has_more": next_cursor is not None,
    }


@router.get(
    "/templates/{template_id}",
    response_model=TemplateResponse,
    dependencies=[Depends(require_role("super_admin", "tenant_admin", "regional_manager"))],
)
async def get_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    template = await service.get_template(db, template_id, user["tenant_id"])
    return TemplateResponse.model_validate(template)


@router.put(
    "/templates/{template_id}",
    response_model=TemplateResponse,
    status_code=201,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def update_template(
    template_id: uuid.UUID,
    data: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    template = await service.update_template(db, template_id, user["tenant_id"], data)
    return TemplateResponse.model_validate(template)


@router.delete(
    "/templates/{template_id}",
    status_code=204,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def delete_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    await service.delete_template(db, template_id, user["tenant_id"])
    return None


@router.post(
    "/templates/{template_id}/approve",
    response_model=TemplateResponse,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def approve_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    template = await service.approve_template(
        db, template_id, user["tenant_id"], user["user_id"]
    )
    return TemplateResponse.model_validate(template)


@router.post(
    "/templates/{template_id}/activate",
    response_model=TemplateResponse,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def activate_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    template = await service.activate_template(db, template_id, user["tenant_id"])
    return TemplateResponse.model_validate(template)


@router.post(
    "/templates/{template_id}/archive",
    response_model=TemplateResponse,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def archive_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    template = await service.archive_template(db, template_id, user["tenant_id"])
    return TemplateResponse.model_validate(template)


@router.get(
    "/templates/{template_id}/versions",
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def get_template_versions(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    versions = await service.get_template_versions(db, template_id, user["tenant_id"])
    return {
        "data": [TemplateVersionResponse.model_validate(v) for v in versions],
    }


@router.post(
    "/templates/{template_id}/preview",
    response_model=TemplatePreviewResponse,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def preview_template(
    template_id: uuid.UUID,
    data: TemplatePreviewRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    rendered, buttons = await service.preview_template(
        db, template_id, user["tenant_id"], data.language, data.params
    )
    return TemplatePreviewResponse(rendered=rendered, buttons=buttons)
