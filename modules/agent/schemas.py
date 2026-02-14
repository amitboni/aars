"""modules/agent/schemas.py — Agent Pydantic schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    agent_code: str = Field(..., max_length=50)
    full_name: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., max_length=15)
    email: str | None = Field(None, max_length=255)
    lifecycle_state: str = "onboarded"
    assigned_adm_id: uuid.UUID | None = None
    license_number: str | None = None
    preferred_language: str = "hi"
    region_node_id: uuid.UUID | None = None


class AgentUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    assigned_adm_id: uuid.UUID | None = None
    license_number: str | None = None
    license_expiry_date: datetime | None = None
    preferred_language: str | None = None
    consent_voice: str | None = None
    consent_whatsapp: str | None = None
    region_node_id: uuid.UUID | None = None


class AgentResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    agent_code: str
    full_name: str
    phone: str
    email: str | None
    lifecycle_state: str
    state_since: datetime
    assigned_adm_id: uuid.UUID | None
    engagement_score: float
    last_positive_signal_at: datetime | None
    last_contact_at: datetime | None
    total_policies_sold: int
    policies_sold_last_12m: int
    dormancy_reason: str | None
    license_number: str | None
    license_expiry_date: datetime | None
    consent_voice: str
    consent_whatsapp: str
    preferred_language: str
    region_node_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
