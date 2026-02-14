"""modules/integration/schemas.py — Pydantic schemas for integration module."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ─── API Response Schemas ───


class UploadResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    total_records: int
    processed: int
    failed: int
    errors: list[dict] = Field(default_factory=list)


class IntegrationJobResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    job_type: str
    source_system: str
    status: str
    file_name: str | None
    total_records: int
    processed_records: int
    failed_records: int
    errors: dict
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebhookPayload(BaseModel):
    source_system: str = Field(..., max_length=30)
    event_type: str = Field(..., max_length=100)
    data: dict = Field(default_factory=dict)
    timestamp: datetime | None = None


class SyncRequest(BaseModel):
    source_system: str = Field(..., max_length=30)


class FieldMappingConfig(BaseModel):
    """Maps insurer field names to AARS field names."""
    mappings: dict[str, str] = Field(default_factory=dict)


# ─── CSV Row Schemas ───


class AgentCSVRow(BaseModel):
    """Spec 3.6.2: agent_master fields."""
    agent_code: str = Field(..., max_length=50)
    full_name: str = Field(..., max_length=200)
    phone: str = Field(..., max_length=15)
    email: str | None = None
    lifecycle_state: str = "onboarded"
    license_number: str | None = None
    license_expiry_date: str | None = None
    preferred_language: str = "hi"
    assigned_adm_id: str | None = None  # adm_assignment
    region_node_id: str | None = None   # region
    onboarding_date: str | None = None


class PolicyCSVRow(BaseModel):
    agent_code: str = Field(..., max_length=50)
    policy_number: str = Field(..., max_length=100)
    product_name: str | None = None
    premium_amount: float | None = None
    policy_date: str | None = None


class CommissionCSVRow(BaseModel):
    agent_code: str = Field(..., max_length=50)
    amount: float
    credit_date: str
    policy_number: str | None = None
    commission_type: str | None = None


class TrainingCSVRow(BaseModel):
    agent_code: str = Field(..., max_length=50)
    training_name: str = Field(..., max_length=200)
    completion_date: str
    score: float | None = None
    status: str = "completed"


class LicenseCSVRow(BaseModel):
    agent_code: str = Field(..., max_length=50)
    license_number: str = Field(..., max_length=50)
    status: str  # active, expired, suspended
    expiry_date: str | None = None
