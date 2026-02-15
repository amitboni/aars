"""modules/settings/schemas.py — Pydantic schemas for settings management."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ─── Settings Read ──────────────────────────────────────────────────────────

class SectionSettingsResponse(BaseModel):
    values: dict
    metadata: dict


class AllSettingsResponse(BaseModel):
    lifecycle_thresholds: SectionSettingsResponse | None = None
    engagement_scoring_weights: SectionSettingsResponse | None = None
    contact_rules: SectionSettingsResponse | None = None
    trai_calling_hours: SectionSettingsResponse | None = None
    rate_limits: SectionSettingsResponse | None = None
    branding: SectionSettingsResponse | None = None
    languages: SectionSettingsResponse | None = None


# ─── Change Request ─────────────────────────────────────────────────────────

class SettingsChangeRequestBody(BaseModel):
    changes: dict = Field(..., min_length=1)


class SettingsChangeRequestResponse(BaseModel):
    change_request_id: uuid.UUID
    otp_sent_to: str
    expires_at: datetime
    changes_summary: dict

    model_config = {"from_attributes": True}


class VerifyOTPBody(BaseModel):
    change_request_id: uuid.UUID
    otp: str = Field(..., min_length=6, max_length=6)


# ─── Audit Log ──────────────────────────────────────────────────────────────

class SettingsAuditLogResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    change_request_id: uuid.UUID
    changed_by: uuid.UUID
    changed_by_email: str
    section: str
    previous_values: dict
    new_values: dict
    changed_fields: list
    verified_at: datetime
    applied_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Change Request Detail ──────────────────────────────────────────────────

class ChangeRequestDetailResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    section: str
    current_values: dict
    proposed_values: dict
    status: str
    otp_attempts: int
    otp_sent_to: str
    otp_expires_at: datetime
    applied_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
