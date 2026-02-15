"""modules/tenant/router.py — Tenant management API routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db_no_tenant, require_role
from modules.tenant import service
from modules.tenant.schemas import TenantCreate, TenantResponse, TenantUpdate

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


@router.post("", response_model=TenantResponse, status_code=201)
async def create_tenant(
    body: TenantCreate,
    current_user: dict = Depends(require_role("super_admin")),
    db: AsyncSession = Depends(get_db_no_tenant),
):
    """Create a new tenant. Super admin only."""
    tenant = await service.create_tenant(db, body)
    await db.commit()
    return TenantResponse.model_validate(tenant)


@router.get("", response_model=dict)
async def list_tenants(
    limit: int = 50,
    cursor: uuid.UUID | None = None,
    current_user: dict = Depends(require_role("super_admin")),
    db: AsyncSession = Depends(get_db_no_tenant),
):
    """List all tenants. Super admin only."""
    tenants, next_cursor = await service.list_tenants(
        db, limit=min(limit, 200), cursor=cursor
    )
    return {
        "data": [TenantResponse.model_validate(t) for t in tenants],
        "next_cursor": str(next_cursor) if next_cursor else None,
        "has_more": next_cursor is not None,
    }


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: uuid.UUID,
    current_user: dict = Depends(require_role("super_admin", "tenant_admin")),
    db: AsyncSession = Depends(get_db_no_tenant),
):
    """Get tenant details. Super admin or own tenant admin."""
    tenant = await service.get_tenant(db, tenant_id)
    return TenantResponse.model_validate(tenant)


@router.put("/{tenant_id}/config", response_model=TenantResponse)
async def update_tenant_config(
    tenant_id: uuid.UUID,
    body: TenantUpdate,
    current_user: dict = Depends(require_role("super_admin")),
    db: AsyncSession = Depends(get_db_no_tenant),
):
    """Update tenant configuration directly. Super admin only.

    DEPRECATED: Use /api/v1/settings endpoints for OTP-protected config changes.
    """
    tenant = await service.update_tenant(db, tenant_id, body)
    await db.commit()
    return TenantResponse.model_validate(tenant)
