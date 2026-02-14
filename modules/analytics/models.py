"""modules/analytics/models.py — Analytics SQLAlchemy models.

Three tables for storing precomputed analytics:
- AnalyticsSnapshot: daily/weekly/monthly metric snapshots
- ReactivationFunnel: contacted -> engaged -> trained -> sold pipeline
- DormancyAnalytics: dormancy reason distribution and trends
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.base_models import Base, TenantScopedMixin


class AnalyticsSnapshot(Base, TenantScopedMixin):
    """Stores precomputed analytics metrics for a given period."""

    __tablename__ = "analytics_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    snapshot_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # DAILY, WEEKLY, MONTHLY
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    def __repr__(self) -> str:
        return f"<AnalyticsSnapshot {self.snapshot_type} {self.snapshot_date}>"


class ReactivationFunnel(Base, TenantScopedMixin):
    """Tracks the reactivation funnel: contacted -> engaged -> trained -> sold."""

    __tablename__ = "reactivation_funnels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    contacted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    engaged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trained_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sold_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    funnel_by_channel: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    funnel_by_playbook: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    def __repr__(self) -> str:
        return f"<ReactivationFunnel {self.period_start} to {self.period_end}>"


class DormancyAnalytics(Base, TenantScopedMixin):
    """Stores dormancy reason distribution snapshots and trends."""

    __tablename__ = "dormancy_analytics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reason_distribution: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    trend_vs_previous: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    regional_breakdown: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    def __repr__(self) -> str:
        return f"<DormancyAnalytics {self.snapshot_date}>"
