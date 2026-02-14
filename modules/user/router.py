"""modules/user/router.py — Auth and user management API routes."""
from __future__ import annotations

import uuid

import jwt
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db, get_db_no_tenant, require_role
from core.security import create_access_token, create_refresh_token, decode_jwt
from core.exceptions import AuthenticationError
from modules.user import service
from modules.user.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.post("/auth/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db_no_tenant)):
    """Register a new user. For initial setup / super_admin invitations."""
    user_data = UserCreate(
        email=body.email,
        full_name=body.full_name,
        phone=body.phone,
        password=body.password,
        roles=body.roles,
    )
    user = await service.create_user(db, body.tenant_id, user_data)
    await db.commit()

    access_token = create_access_token(
        user_id=user.id, tenant_id=user.tenant_id, roles=list(user.roles)
    )
    refresh_token = create_refresh_token(user_id=user.id, tenant_id=user.tenant_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db_no_tenant)):
    """Authenticate with email and password."""
    user, tokens = await service.authenticate_user(db, body.email, body.password)
    await db.commit()
    return tokens


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db_no_tenant)):
    """Exchange a refresh token for a new access + refresh token pair."""
    try:
        payload = decode_jwt(body.refresh_token)
    except jwt.PyJWTError:
        raise AuthenticationError("Invalid or expired refresh token")

    if payload.get("type") != "refresh":
        raise AuthenticationError("Token is not a refresh token")

    user = await service.get_user_for_refresh(db, payload["user_id"])

    access_token = create_access_token(
        user_id=user.id, tenant_id=user.tenant_id, roles=list(user.roles)
    )
    new_refresh_token = create_refresh_token(user_id=user.id, tenant_id=user.tenant_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.get("/auth/me", response_model=UserResponse)
async def get_me(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get the current authenticated user's profile."""
    user = await service.get_user_by_id(
        db, current_user["user_id"], current_user["tenant_id"]
    )
    return UserResponse.model_validate(user)


@router.get("/users", response_model=dict)
async def list_users(
    limit: int = 50,
    cursor: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("super_admin", "tenant_admin")),
):
    """List users in the current tenant. Requires tenant_admin or super_admin."""
    users, next_cursor = await service.list_users(
        db, current_user["tenant_id"], limit=min(limit, 200), cursor=cursor
    )
    return {
        "data": [UserResponse.model_validate(u) for u in users],
        "next_cursor": str(next_cursor) if next_cursor else None,
        "has_more": next_cursor is not None,
    }
