"""core/tenant_context.py — Tenant context propagation via contextvars."""
from __future__ import annotations

import uuid
from contextvars import ContextVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

_current_tenant_id: ContextVar[uuid.UUID | None] = ContextVar("tenant_id", default=None)
_current_user_id: ContextVar[uuid.UUID | None] = ContextVar("user_id", default=None)
_current_user_roles: ContextVar[list[str]] = ContextVar("user_roles", default=[])


def get_tenant_id() -> uuid.UUID:
    tid = _current_tenant_id.get()
    if tid is None:
        raise RuntimeError("Tenant context not set")
    return tid


def get_user_id() -> uuid.UUID:
    uid = _current_user_id.get()
    if uid is None:
        raise RuntimeError("User context not set")
    return uid


def get_user_roles() -> list[str]:
    return _current_user_roles.get()


def set_context(tenant_id: uuid.UUID, user_id: uuid.UUID, roles: list[str]) -> None:
    _current_tenant_id.set(tenant_id)
    _current_user_id.set(user_id)
    _current_user_roles.set(roles)


def clear_context() -> None:
    _current_tenant_id.set(None)
    _current_user_id.set(None)
    _current_user_roles.set([])


async def set_rls_context_async(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Set PostgreSQL session variable for RLS. Used in FastAPI handlers.
    Note: SET LOCAL does not support parameterized queries in asyncpg,
    so we use literal formatting. Safe because tenant_id is a validated UUID."""
    tid = str(uuid.UUID(str(tenant_id)))  # Re-validate to ensure it's a valid UUID
    await session.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))


def set_rls_context_sync(session: Session, tenant_id: uuid.UUID) -> None:
    """Set PostgreSQL session variable for RLS. Used in Celery tasks."""
    session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})
