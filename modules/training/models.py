"""modules/training/models.py — Training SQLAlchemy models."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import Base, TenantScopedMixin, SoftDeleteMixin, TimestampMixin


class TrainingModule(Base, TenantScopedMixin, SoftDeleteMixin):
    """A training module with content and metadata."""

    __tablename__ = "training_modules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, default="beginner")
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="hi")

    # Content
    content_type: Mapped[str] = mapped_column(String(20), nullable=False, default="video")
    file_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Performance metrics
    effectiveness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    times_assigned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Expiry
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    quiz = relationship(
        "TrainingQuiz",
        back_populates="training_module",
        uselist=False,
        lazy="selectin",
    )
    tenant = relationship("Tenant", lazy="selectin")

    def __repr__(self) -> str:
        return f"<TrainingModule {self.title} ({self.id})>"


class TrainingQuiz(Base, TimestampMixin):
    """Quiz associated with a training module. Not tenant-scoped — accessed via training_module."""

    __tablename__ = "training_quizzes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    training_module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("training_modules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Questions: [{"question": str, "options": [str], "correct": int, "explanation": str}]
    questions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    passing_score: Mapped[int] = mapped_column(Integer, nullable=False, default=70)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    training_module = relationship("TrainingModule", back_populates="quiz")

    def __repr__(self) -> str:
        return f"<TrainingQuiz module={self.training_module_id} questions={len(self.questions)}>"


class TrainingProgress(Base, TenantScopedMixin):
    """Tracks an agent's progress through a training module. No soft delete."""

    __tablename__ = "training_progress"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    training_module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("training_modules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Progress
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="assigned", index=True
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Assignment source
    assigned_by: Mapped[str] = mapped_column(String(50), nullable=False, default="system")
    playbook_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    def __repr__(self) -> str:
        return f"<TrainingProgress module={self.training_module_id} agent={self.agent_id} status={self.status}>"
