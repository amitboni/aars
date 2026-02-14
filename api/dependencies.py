"""api/dependencies.py — FastAPI dependency injection."""
from __future__ import annotations

import uuid
from typing import AsyncGenerator

import jwt
from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import async_session_factory
from core.security import decode_jwt
from core.tenant_context import set_context, set_rls_context_async


async def get_db_no_tenant() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session WITHOUT tenant RLS context.
    Used for auth endpoints and super_admin operations that span tenants."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_current_user(authorization: str = Header(...)) -> dict:
    """Extract and validate JWT, set tenant context."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization[7:]  # Strip "Bearer "
    try:
        payload = decode_jwt(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    set_context(
        tenant_id=payload["tenant_id"],
        user_id=payload["user_id"],
        roles=payload.get("roles", []),
    )
    return payload


async def get_db(
    current_user: dict = Depends(get_current_user),
) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session with RLS context set.
    Depends on get_current_user to ensure tenant context is available."""
    async with async_session_factory() as session:
        await set_rls_context_async(session, current_user["tenant_id"])
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def require_role(*roles: str):
    """Dependency that checks the user has one of the required roles."""
    async def checker(user: dict = Depends(get_current_user)):
        if not any(r in user.get("roles", []) for r in roles):
            raise HTTPException(403, "Insufficient permissions")
        return user
    return checker
