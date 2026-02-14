"""modules/decision/models.py — Decision Engine SQLAlchemy models.

Per spec section 4.15 Slice 7: decision_logs table with full reasoning.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.base_models import Base, TenantScopedMixin


class DecisionLog(Base, TenantScopedMixin):
    __tablename__ = "decision_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    adm_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    rule_id: Mapped[str] = mapped_column(String(50), nullable=False)
    decision_action: Mapped[str] = mapped_column(String(50), nullable=False)
    playbook_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    channel: Mapped[str | None] = mapped_column(String(30), nullable=True)
    language: Mapped[str | None] = mapped_column(String(5), nullable=True)
    priority: Mapped[str] = mapped_column(
        String(10), nullable=False, default="MEDIUM"
    )
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    execution_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<DecisionLog {self.rule_id} action={self.decision_action} agent={self.agent_id}>"
