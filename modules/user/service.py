"""modules/user/service.py — User CRUD and auth operations."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConflictError, NotFoundError, AuthenticationError
from core.security import hash_password, verify_password, create_access_token, create_refresh_token
from modules.user.models import User
from modules.user.schemas import UserCreate, TokenResponse, UserResponse


async def create_user(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: UserCreate,
) -> User:
    """Create a new user within a tenant. Raises ConflictError if email exists."""
    existing = await db.execute(
        select(User).where(
            User.tenant_id == tenant_id,
            User.email == data.email.lower().strip(),
            User.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(
            f"User with email {data.email} already exists in this tenant",
            details={"email": data.email},
        )

    user = User(
        tenant_id=tenant_id,
        email=data.email.lower().strip(),
        full_name=data.full_name.strip(),
        phone=data.phone,
        password_hash=hash_password(data.password),
        roles=data.roles,
    )
    db.add(user)
    await db.flush()
    return user


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> tuple[User, TokenResponse]:
    """Authenticate user by email+password across all tenants. Returns user and tokens."""
    result = await db.execute(
        select(User).where(
            User.email == email.lower().strip(),
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid email or password")

    access_token = create_access_token(
        user_id=user.id, tenant_id=user.tenant_id, roles=list(user.roles)
    )
    refresh_token = create_refresh_token(user_id=user.id, tenant_id=user.tenant_id)

    return user, TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID, tenant_id: uuid.UUID) -> User:
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.tenant_id == tenant_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User", user_id)
    return user


async def get_user_for_refresh(db: AsyncSession, user_id: uuid.UUID) -> User:
    """Get a user by ID for token refresh (no tenant filter — tenant comes from token)."""
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise AuthenticationError("User not found or inactive")
    return user


async def list_users(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 50,
    cursor: uuid.UUID | None = None,
) -> tuple[list[User], uuid.UUID | None]:
    """List users with cursor-based pagination."""
    query = (
        select(User)
        .where(User.tenant_id == tenant_id, User.deleted_at.is_(None))
        .order_by(User.created_at.desc(), User.id)
        .limit(limit + 1)
    )
    if cursor:
        cursor_user = await db.get(User, cursor)
        if cursor_user:
            query = query.where(
                (User.created_at < cursor_user.created_at)
                | ((User.created_at == cursor_user.created_at) & (User.id > cursor_user.id))
            )

    result = await db.execute(query)
    users = list(result.scalars().all())

    next_cursor = None
    if len(users) > limit:
        users = users[:limit]
        next_cursor = users[-1].id

    return users, next_cursor
