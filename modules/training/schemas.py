"""modules/training/schemas.py — Training Pydantic schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ─── Training Module ─────────────────────────────────────────────────────────

class TrainingModuleCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    topic: str = Field(..., max_length=50)
    difficulty: str = Field("beginner", max_length=20)
    duration_minutes: int = Field(..., ge=1)
    language: str = Field("hi", max_length=5)
    content_type: str = Field("video", max_length=20)
    file_url: str | None = None
    expires_at: datetime | None = None


class TrainingModuleUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    topic: str | None = None
    difficulty: str | None = None
    duration_minutes: int | None = None
    language: str | None = None
    content_type: str | None = None
    file_url: str | None = None
    is_active: bool | None = None
    expires_at: datetime | None = None


class TrainingModuleResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    description: str | None
    topic: str
    difficulty: str
    duration_minutes: int
    language: str
    content_type: str
    file_key: str | None
    file_url: str | None
    file_size_bytes: int | None
    thumbnail_key: str | None
    is_active: bool
    is_default: bool
    effectiveness_score: float
    times_assigned: int
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TrainingModuleSummaryResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    topic: str
    difficulty: str
    duration_minutes: int
    is_active: bool
    is_default: bool
    times_assigned: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Quiz ────────────────────────────────────────────────────────────────────

class QuizCreate(BaseModel):
    questions: list = Field(..., min_length=1)
    passing_score: int = Field(70, ge=0, le=100)
    max_attempts: int = Field(3, ge=1)


class QuizResponse(BaseModel):
    id: uuid.UUID
    training_module_id: uuid.UUID
    questions: list
    passing_score: int
    max_attempts: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QuizQuestionResponse(BaseModel):
    question: str
    options: list[str]
    correct: int
    explanation: str | None = None


# ─── Training Progress ──────────────────────────────────────────────────────

class TrainingProgressCreate(BaseModel):
    training_module_id: uuid.UUID
    agent_id: uuid.UUID
    assigned_by: str = "system"
    playbook_run_id: uuid.UUID | None = None


class TrainingProgressUpdate(BaseModel):
    status: str | None = None
    score: float | None = None
    attempts: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class TrainingProgressResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    training_module_id: uuid.UUID
    agent_id: uuid.UUID
    status: str
    score: float | None
    attempts: int
    started_at: datetime | None
    completed_at: datetime | None
    assigned_by: str
    playbook_run_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
