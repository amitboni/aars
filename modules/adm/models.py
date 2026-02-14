"""modules/adm/models.py — ADM Experience SQLAlchemy models.

Tables: morning_briefings, adm_actions, adm_alerts, weekly_summaries.
All tenant-scoped with RLS policies.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.base_models import Base, TenantScopedMixin


class MorningBriefing(Base, TenantScopedMixin):
    __tablename__ = "morning_briefings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    adm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    briefing_date: Mapped[Date] = mapped_column(Date, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    delivered_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    read_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<MorningBriefing adm={self.adm_id} date={self.briefing_date}>"


class ADMAction(Base, TenantScopedMixin):
    __tablename__ = "adm_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    adm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # CALLED_AGENT, VISITED_AGENT, SENT_TRAINING, ESCALATED, ACKNOWLEDGED, FORWARDED_CONTENT
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, default="MANUAL"
    )  # NUDGE_REPLY, QUICK_LOG, VOICE_NOTE_LOG, MANUAL
    nudge_reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<ADMAction {self.action_type} adm={self.adm_id} agent={self.agent_id}>"


class ADMAlert(Base, TenantScopedMixin):
    __tablename__ = "adm_alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    adm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    alert_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # REENGAGEMENT_SIGNAL, TRAINING_COMPLETED, OPTED_OUT, LICENSE_EXPIRING, ESCALATION
    urgency: Mapped[str] = mapped_column(
        String(10), nullable=False, default="MEDIUM"
    )  # LOW, MEDIUM, HIGH, CRITICAL
    message: Mapped[str] = mapped_column(Text, nullable=False)
    delivered_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    read_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acted_on_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<ADMAlert {self.alert_type} urgency={self.urgency} adm={self.adm_id}>"


class WeeklySummary(Base, TenantScopedMixin):
    __tablename__ = "weekly_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    adm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    week_start: Mapped[Date] = mapped_column(Date, nullable=False)
    week_end: Mapped[Date] = mapped_column(Date, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    delivered_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    read_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<WeeklySummary adm={self.adm_id} {self.week_start}–{self.week_end}>"
