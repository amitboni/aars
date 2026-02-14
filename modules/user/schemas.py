"""modules/user/schemas.py — Pydantic schemas for User."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: str = Field(..., max_length=255)
    full_name: str = Field(..., min_length=1, max_length=200)
    phone: str | None = Field(None, max_length=15)
    password: str = Field(..., min_length=8, max_length=128)
    roles: list[str] = Field(default_factory=lambda: ["adm"])


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=200)
    phone: str | None = None
    roles: list[str] | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    roles: list[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterRequest(BaseModel):
    email: str = Field(..., max_length=255)
    full_name: str = Field(..., min_length=1, max_length=200)
    phone: str | None = Field(None, max_length=15)
    password: str = Field(..., min_length=8, max_length=128)
    tenant_id: uuid.UUID
    roles: list[str] = Field(default_factory=lambda: ["adm"])
