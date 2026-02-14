"""modules/integration/models.py — IntegrationJob tracking model."""
from __future__ import annotations

import uuid

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.base_models import Base, TenantScopedMixin


class IntegrationJob(Base, TenantScopedMixin):
    """Tracks each CSV upload / webhook / API sync operation."""

    __tablename__ = "integration_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_type: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )  # csv_upload, webhook, api_sync
    source_system: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )  # pas, lms, commission
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, processing, completed, failed
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<IntegrationJob {self.job_type}:{self.source_system} status={self.status} ({self.id})>"
