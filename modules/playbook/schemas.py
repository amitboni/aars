"""modules/playbook/schemas.py — Playbook Pydantic schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ─── Step schemas ────────────────────────────────────────────────────────────

class PlaybookStepCreate(BaseModel):
    step_number: int = Field(..., ge=1)
    name: str = Field(..., min_length=1, max_length=200)
    action_type: str = Field(..., max_length=30)
    action_config: dict = Field(default_factory=dict)
    delay_days: int = Field(0, ge=0)
    next_step_rules: list = Field(default_factory=list)


class PlaybookStepResponse(BaseModel):
    id: uuid.UUID
    playbook_id: uuid.UUID
    step_number: int
    name: str
    action_type: str
    action_config: dict
    delay_days: int
    next_step_rules: list
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Playbook schemas ───────────────────────────────────────────────────────

class PlaybookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    trigger_conditions: dict = Field(default_factory=dict)
    success_criteria: dict = Field(default_factory=dict)
    max_duration_days: int = Field(30, ge=1)
    steps: list[PlaybookStepCreate] = Field(default_factory=list)


class PlaybookUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    trigger_conditions: dict | None = None
    success_criteria: dict | None = None
    max_duration_days: int | None = None


class PlaybookResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    is_default: bool
    trigger_conditions: dict
    success_criteria: dict
    max_duration_days: int
    times_executed: int
    success_rate: float
    steps: list[PlaybookStepResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlaybookSummaryResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    is_default: bool
    max_duration_days: int
    times_executed: int
    success_rate: float
    steps_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Run schemas ─────────────────────────────────────────────────────────────

class PlaybookTrigger(BaseModel):
    """Request to trigger a playbook for an agent."""
    playbook_id: uuid.UUID
    agent_id: uuid.UUID
    context: dict = Field(default_factory=dict)


class PlaybookRunResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    playbook_id: uuid.UUID
    agent_id: uuid.UUID
    status: str
    current_step_number: int
    context: dict
    started_at: datetime
    completed_at: datetime | None
    next_step_due_at: datetime | None
    outcome: str | None
    steps_executed: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PlaybookStepRunResponse(BaseModel):
    id: uuid.UUID
    playbook_run_id: uuid.UUID
    playbook_step_id: uuid.UUID
    step_number: int
    status: str
    executed_at: datetime | None
    outcome: str | None
    outcome_details: dict
    next_step_number: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
