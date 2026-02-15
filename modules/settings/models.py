"""modules/settings/models.py — Settings change request and audit log SQLAlchemy models."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.base_models import Base, TimestampMixin


class SettingsChangeRequest(Base, TimestampMixin):
    """Tracks a proposed settings change through OTP verification."""

    __tablename__ = "settings_change_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    section: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    current_values: Mapped[dict] = mapped_column(JSONB, nullable=False)
    proposed_values: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # OTP verification
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending_otp", index=True
    )
    otp_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    otp_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    otp_sent_to: Mapped[str] = mapped_column(String(255), nullable=False)
    otp_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<SettingsChangeRequest {self.section} "
            f"status={self.status} ({self.id})>"
        )


class SettingsAuditLog(Base, TimestampMixin):
    """Immutable audit log of applied settings changes."""

    __tablename__ = "settings_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    change_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("settings_change_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    changed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    changed_by_email: Mapped[str] = mapped_column(String(255), nullable=False)
    section: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    previous_values: Mapped[dict] = mapped_column(JSONB, nullable=False)
    new_values: Mapped[dict] = mapped_column(JSONB, nullable=False)
    changed_fields: Mapped[list] = mapped_column(JSONB, nullable=False)
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return f"<SettingsAuditLog {self.section} by={self.changed_by_email} ({self.id})>"
