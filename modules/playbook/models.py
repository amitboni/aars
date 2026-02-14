"""modules/playbook/models.py — Playbook SQLAlchemy models."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import Base, TenantScopedMixin, SoftDeleteMixin, TimestampMixin


class Playbook(Base, TenantScopedMixin, SoftDeleteMixin):
    """Playbook definition — a reusable template of steps."""

    __tablename__ = "playbooks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Trigger conditions (JSONB for flexibility)
    trigger_conditions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Success criteria
    success_criteria: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    max_duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    # Performance metrics (updated periodically)
    times_executed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    steps = relationship(
        "PlaybookStep",
        back_populates="playbook",
        order_by="PlaybookStep.step_number",
        lazy="selectin",
    )

    tenant = relationship("Tenant", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Playbook {self.name} ({self.id})>"


class PlaybookStep(Base, TimestampMixin):
    """A single step within a playbook definition."""

    __tablename__ = "playbook_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    playbook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("playbooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Action config
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    action_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Scheduling
    delay_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Branching rules (list of {condition, go_to_step or action})
    next_step_rules: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    playbook = relationship("Playbook", back_populates="steps")

    def __repr__(self) -> str:
        return f"<PlaybookStep {self.step_number}: {self.name} ({self.id})>"


class PlaybookRun(Base, TenantScopedMixin):
    """An active execution of a playbook for a specific agent."""

    __tablename__ = "playbook_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    playbook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("playbooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="in_progress"
    )  # in_progress, completed, failed, paused, expired
    current_step_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Mutable context carried between steps
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # When the next step should execute
    next_step_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)

    steps_executed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    playbook = relationship("Playbook", lazy="selectin")

    def __repr__(self) -> str:
        return f"<PlaybookRun playbook={self.playbook_id} agent={self.agent_id} status={self.status}>"


class PlaybookStepRun(Base, TimestampMixin):
    """Tracks execution of a single step within a playbook run."""

    __tablename__ = "playbook_step_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    playbook_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("playbook_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    playbook_step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("playbook_steps.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending"
    )  # pending, executing, completed, skipped, failed

    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    outcome: Mapped[str | None] = mapped_column(String(100), nullable=True)
    outcome_details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Which step to go to next (resolved by condition evaluator)
    next_step_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<PlaybookStepRun step={self.step_number} status={self.status}>"
