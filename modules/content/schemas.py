"""modules/content/schemas.py — Message template Pydantic schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ─── Template CRUD ──────────────────────────────────────────────────────────

class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., max_length=30)
    description: str | None = None
    language_variants: dict = Field(default_factory=dict)
    placeholders: list = Field(default_factory=list)
    buttons: list = Field(default_factory=list)
    meta_template_id: str | None = None


class TemplateUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    description: str | None = None
    language_variants: dict | None = None
    placeholders: list | None = None
    buttons: list | None = None
    meta_template_id: str | None = None


class TemplateResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    category: str
    description: str | None
    language_variants: dict
    placeholders: list
    buttons: list
    status: str
    version: int
    previous_version_id: uuid.UUID | None
    meta_template_id: str | None
    is_default: bool
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateSummaryResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    category: str
    description: str | None
    status: str
    version: int
    is_default: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Preview ─────────────────────────────────────────────────────────────────

class TemplatePreviewRequest(BaseModel):
    language: str = Field("hi", max_length=5)
    params: dict = Field(default_factory=dict)


class TemplatePreviewResponse(BaseModel):
    rendered: str
    buttons: list


# ─── Versions ────────────────────────────────────────────────────────────────

class TemplateVersionResponse(BaseModel):
    id: uuid.UUID
    version: int
    status: str
    previous_version_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Usage Log ───────────────────────────────────────────────────────────────

class TemplateUsageResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    template_id: uuid.UUID
    template_version: int
    agent_id: uuid.UUID
    playbook_run_id: uuid.UUID | None
    rendered_content: str
    language_used: str
    channel: str
    sent_at: datetime
    delivered_at: datetime | None
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
