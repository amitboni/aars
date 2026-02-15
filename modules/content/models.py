"""modules/content/models.py — Message template SQLAlchemy models."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import Base, TenantScopedMixin, SoftDeleteMixin, TimestampMixin


class MessageTemplate(Base, TenantScopedMixin, SoftDeleteMixin):
    """Per-tenant message template with language variants and versioning."""

    __tablename__ = "message_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Full message content per language: {"hi": "...", "en": "..."}
    language_variants: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Placeholder definitions: [{"key": "agent_name", "description": "...", "required": true}]
    placeholders: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Button definitions: [{"label": "...", "type": "quick_reply"}]
    buttons: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Workflow status: draft -> in_review -> approved -> active -> archived
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)

    # Versioning
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    previous_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("message_templates.id"),
        nullable=True,
    )

    # Meta WhatsApp Business API template ID
    meta_template_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Seeded default templates
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Approval tracking
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant = relationship("Tenant", lazy="selectin")

    def __repr__(self) -> str:
        return f"<MessageTemplate {self.name} v{self.version} ({self.id}) status={self.status}>"


class TemplateUsageLog(Base, TimestampMixin):
    """Append-only audit log of template usage. No soft delete, no TenantScopedMixin."""

    __tablename__ = "template_usage_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("message_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_version: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    playbook_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Actual rendered content for compliance audit
    rendered_content: Mapped[str] = mapped_column(Text, nullable=False)
    language_used: Mapped[str] = mapped_column(String(5), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)

    # Delivery tracking
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<TemplateUsageLog template={self.template_id} agent={self.agent_id}>"
