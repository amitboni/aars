"""modules/signal/schemas.py — Signal Pydantic schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SignalEmit(BaseModel):
    """Schema for emitting a new signal via API."""
    signal_type: str = Field(..., max_length=100)
    source: str = Field(..., max_length=50)
    agent_id: uuid.UUID | None = None
    adm_id: uuid.UUID | None = None
    timestamp: datetime | None = None  # Defaults to now if not provided
    channel: str | None = None
    conversation_id: uuid.UUID | None = None
    payload: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)
    idempotency_key: str | None = Field(None, max_length=200)


class SignalResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    signal_type: str
    source: str
    agent_id: uuid.UUID | None
    adm_id: uuid.UUID | None
    timestamp: datetime
    channel: str | None
    conversation_id: uuid.UUID | None
    payload: dict
    metadata: dict = Field(alias="metadata_")
    idempotency_key: str | None
    processed: bool
    processed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}
