"""modules/decision/schemas.py — Decision Engine Pydantic schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DecisionInput(BaseModel):
    """Internal model: all data needed to evaluate an agent."""
    agent_id: uuid.UUID
    tenant_id: uuid.UUID
    lifecycle_state: str
    days_in_state: int = 0
    previous_state: str | None = None

    engagement_score: float = 0.0
    last_positive_signal_at: datetime | None = None
    last_contact_at: datetime | None = None

    # Consent
    consent: dict[str, str] = Field(default_factory=dict)

    # Dormancy
    dormancy_reason: str | None = None
    reactivation_attempts: int = 0
    reactivation_probability: float = 0.5

    # Sales
    total_policies: int = 0
    last_sale_date: datetime | None = None
    policies_last_12m: int = 0

    # Capability
    training_modules_completed: int = 0
    license_expiry_date: datetime | None = None
    training_hours_remaining: float = 0.0

    # ADM
    adm_id: uuid.UUID | None = None
    adm_nudge_response_rate: float = 0.5
    adm_classification: str = "AVERAGE"

    # Playbook
    active_playbook_id: uuid.UUID | None = None

    # Contact frequency
    contacts_this_month: int = 0

    # DND
    dnd_registered: bool = False
    dnd_call_classification_confirmed: bool = False


class DecisionOutput(BaseModel):
    """Result of evaluating an agent."""
    action: str  # DecisionAction enum value
    rule_id: str
    playbook_id: uuid.UUID | None = None
    scheduled_time: datetime
    channel: str | None = None
    language: str | None = None
    priority: str = "MEDIUM"
    reasoning: str = ""


class DecisionLogResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    agent_id: uuid.UUID
    adm_id: uuid.UUID | None = None
    rule_id: str
    decision_action: str
    playbook_id: uuid.UUID | None = None
    channel: str | None = None
    language: str | None = None
    priority: str
    reasoning: str
    scheduled_time: datetime
    executed: bool
    executed_at: datetime | None = None
    execution_result: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
