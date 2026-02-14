"""modules/tenant/service.py — Tenant CRUD operations."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConflictError, NotFoundError
from modules.tenant.models import Tenant
from modules.tenant.schemas import TenantCreate, TenantUpdate


async def create_tenant(db: AsyncSession, data: TenantCreate) -> Tenant:
    """Create a new tenant. Raises ConflictError if slug already exists."""
    existing = await db.execute(
        select(Tenant).where(Tenant.slug == data.slug)
    )
    if existing.scalar_one_or_none():
        raise ConflictError(
            f"Tenant with slug '{data.slug}' already exists",
            details={"slug": data.slug},
        )

    tenant = Tenant(
        name=data.name,
        slug=data.slug,
        subscription_tier=data.subscription_tier,
        config=data.config,
    )
    db.add(tenant)
    await db.flush()
    return tenant


async def get_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise NotFoundError("Tenant", tenant_id)
    return tenant


async def get_tenant_by_slug(db: AsyncSession, slug: str) -> Tenant | None:
    """Look up a tenant by slug. Returns None if not found."""
    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    return result.scalar_one_or_none()


async def update_tenant(
    db: AsyncSession, tenant_id: uuid.UUID, data: TenantUpdate
) -> Tenant:
    tenant = await get_tenant(db, tenant_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tenant, field, value)
    await db.flush()
    return tenant


async def list_tenants(
    db: AsyncSession,
    limit: int = 50,
    cursor: uuid.UUID | None = None,
) -> tuple[list[Tenant], uuid.UUID | None]:
    """List all tenants (super_admin only). Cursor-based pagination."""
    query = select(Tenant).order_by(Tenant.created_at.desc(), Tenant.id).limit(limit + 1)
    if cursor:
        cursor_tenant = await db.get(Tenant, cursor)
        if cursor_tenant:
            query = query.where(
                (Tenant.created_at < cursor_tenant.created_at)
                | ((Tenant.created_at == cursor_tenant.created_at) & (Tenant.id > cursor_tenant.id))
            )

    result = await db.execute(query)
    tenants = list(result.scalars().all())

    next_cursor = None
    if len(tenants) > limit:
        tenants = tenants[:limit]
        next_cursor = tenants[-1].id

    return tenants, next_cursor
