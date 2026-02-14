"""modules/tenant/schemas.py — Pydantic schemas for Tenant."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9\-]+$")
    subscription_tier: str = Field(default="trial")
    config: dict = Field(default_factory=dict)


class TenantUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    subscription_tier: str | None = None
    is_active: bool | None = None
    config: dict | None = None


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    subscription_tier: str
    is_active: bool
    config: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
