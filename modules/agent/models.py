"""modules/agent/models.py — Agent SQLAlchemy model."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Float, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import Base, TenantScopedMixin, SoftDeleteMixin


class Agent(Base, TenantScopedMixin, SoftDeleteMixin):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_code: Mapped[str] = mapped_column(String(50), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(15), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Lifecycle
    lifecycle_state: Mapped[str] = mapped_column(
        String(30), nullable=False, default="onboarded", index=True
    )
    state_since: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default="now()",
    )

    # Organization
    assigned_adm_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    # Engagement summary (updated by signal processing)
    engagement_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_positive_signal_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_contact_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Sales summary
    total_policies_sold: Mapped[int] = mapped_column(nullable=False, default=0)
    policies_sold_last_12m: Mapped[int] = mapped_column(nullable=False, default=0)

    # Dormancy
    dormancy_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # License
    license_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    license_expiry_date: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Consent
    consent_voice: Mapped[str] = mapped_column(String(20), nullable=False, default="not_asked")
    consent_whatsapp: Mapped[str] = mapped_column(String(20), nullable=False, default="not_asked")

    # Preferred language
    preferred_language: Mapped[str] = mapped_column(String(5), nullable=False, default="hi")

    # Region
    region_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    tenant = relationship("Tenant", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Agent {self.agent_code} ({self.id}) state={self.lifecycle_state}>"
