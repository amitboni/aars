"""modules/analytics/router.py — Analytics API routes.

9 endpoints under /api/v1/analytics/:
- GET /dashboard              — executive dashboard metrics
- GET /dormancy               — dormancy reason distribution and trends
- GET /reactivation-funnel    — contacted -> engaged -> trained -> sold
- GET /adm-performance        — ADM performance rankings
- GET /training-effectiveness — training module effectiveness
- GET /system-roi             — system ROI calculation
- GET /reports/dormancy       — stored dormancy intelligence report
- GET /reports/training       — stored training effectiveness report
- GET /reports/adm            — stored ADM performance report

Role-based data scoping:
- tenant_admin, analyst: see all data
- regional_manager: see only their region (region_node_id from JWT)
- adm: see only their assigned agents (limited access)
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_role
from core.enums import UserRole
from modules.analytics import service
from modules.analytics.models import AnalyticsSnapshot, DormancyAnalytics, ReactivationFunnel
from modules.analytics.schemas import (
    ADMPerformanceResponse,
    DashboardResponse,
    DormancyAnalyticsResponse,
    ReactivationFunnelResponse,
    ReportResponse,
    SystemROIResponse,
    TrainingEffectivenessResponse,
)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


def _to_uuid(value) -> uuid.UUID:
    """Convert a value to UUID, handling both str and UUID inputs."""
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _get_region_scope(user: dict) -> uuid.UUID | None:
    """Extract region_node_id for regional managers, None for admins."""
    roles = user.get("roles", [])
    if UserRole.TENANT_ADMIN in roles or UserRole.ANALYST in roles:
        return None  # Full access
    return user.get("region_node_id")


# ─── Live Analytics ───


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(
        UserRole.TENANT_ADMIN, UserRole.ANALYST, UserRole.REGIONAL_MANAGER,
    )),
):
    """Executive dashboard metrics (spec section 3.7.1)."""
    tenant_id = _to_uuid(user["tenant_id"])
    region_node_id = _get_region_scope(user)
    return await service.get_dashboard(db, tenant_id, region_node_id)


@router.get("/dormancy", response_model=DormancyAnalyticsResponse)
async def get_dormancy_analytics(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(
        UserRole.TENANT_ADMIN, UserRole.ANALYST, UserRole.REGIONAL_MANAGER,
    )),
):
    """Dormancy reason distribution and trends."""
    tenant_id = _to_uuid(user["tenant_id"])
    region_node_id = _get_region_scope(user)
    return await service.get_dormancy_analytics(db, tenant_id, region_node_id)


@router.get("/reactivation-funnel", response_model=ReactivationFunnelResponse)
async def get_reactivation_funnel(
    period_days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(
        UserRole.TENANT_ADMIN, UserRole.ANALYST, UserRole.REGIONAL_MANAGER,
    )),
):
    """Reactivation funnel: contacted -> engaged -> trained -> sold."""
    tenant_id = _to_uuid(user["tenant_id"])
    return await service.get_reactivation_funnel(db, tenant_id, period_days)


@router.get("/adm-performance", response_model=ADMPerformanceResponse)
async def get_adm_performance(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(
        UserRole.TENANT_ADMIN, UserRole.ANALYST,
    )),
):
    """ADM performance rankings (spec section 3.7.2)."""
    tenant_id = _to_uuid(user["tenant_id"])
    return await service.get_adm_performance(db, tenant_id)


@router.get("/training-effectiveness", response_model=TrainingEffectivenessResponse)
async def get_training_effectiveness(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(
        UserRole.TENANT_ADMIN, UserRole.ANALYST,
    )),
):
    """Training module effectiveness metrics."""
    tenant_id = _to_uuid(user["tenant_id"])
    return await service.get_training_effectiveness(db, tenant_id)


@router.get("/system-roi", response_model=SystemROIResponse)
async def get_system_roi(
    period_days: int = Query(30, ge=7, le=365),
    system_cost: float = Query(50000.0, gt=0),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(
        UserRole.TENANT_ADMIN,
    )),
):
    """System ROI calculation."""
    tenant_id = _to_uuid(user["tenant_id"])
    return await service.get_system_roi(db, tenant_id, period_days, system_cost)


# ─── Stored Reports ───


@router.get("/reports/dormancy", response_model=ReportResponse)
async def get_dormancy_report(
    report_date: date | None = Query(None, description="Specific date, defaults to latest"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(
        UserRole.TENANT_ADMIN, UserRole.ANALYST, UserRole.REGIONAL_MANAGER,
    )),
):
    """Retrieve stored dormancy intelligence report."""
    tenant_id = _to_uuid(user["tenant_id"])

    q = select(DormancyAnalytics).where(
        DormancyAnalytics.tenant_id == tenant_id,
    )
    if report_date:
        q = q.where(DormancyAnalytics.snapshot_date == report_date)
    q = q.order_by(DormancyAnalytics.snapshot_date.desc()).limit(1)

    result = await db.execute(q)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(404, "No dormancy report found")

    return ReportResponse(
        report_type="dormancy_intelligence",
        generated_at=record.created_at,
        tenant_id=record.tenant_id,
        period_start=record.snapshot_date - timedelta(days=30),
        period_end=record.snapshot_date,
        data={
            "reason_distribution": record.reason_distribution,
            "trend_vs_previous": record.trend_vs_previous,
            "regional_breakdown": record.regional_breakdown,
        },
    )


@router.get("/reports/training", response_model=ReportResponse)
async def get_training_report(
    report_date: date | None = Query(None, description="Specific date, defaults to latest"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(
        UserRole.TENANT_ADMIN, UserRole.ANALYST,
    )),
):
    """Retrieve stored training effectiveness report."""
    tenant_id = _to_uuid(user["tenant_id"])

    q = select(AnalyticsSnapshot).where(
        AnalyticsSnapshot.tenant_id == tenant_id,
        AnalyticsSnapshot.snapshot_type == "MONTHLY",
    )
    if report_date:
        q = q.where(AnalyticsSnapshot.snapshot_date == report_date)
    q = q.order_by(AnalyticsSnapshot.snapshot_date.desc()).limit(1)

    result = await db.execute(q)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(404, "No training report found")

    return ReportResponse(
        report_type="training_effectiveness",
        generated_at=record.created_at,
        tenant_id=record.tenant_id,
        period_start=record.snapshot_date - timedelta(days=90),
        period_end=record.snapshot_date,
        data=record.metrics.get("training_effectiveness", {}),
    )


@router.get("/reports/adm", response_model=ReportResponse)
async def get_adm_report(
    report_date: date | None = Query(None, description="Specific date, defaults to latest"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(
        UserRole.TENANT_ADMIN, UserRole.ANALYST,
    )),
):
    """Retrieve stored ADM performance report."""
    tenant_id = _to_uuid(user["tenant_id"])

    q = select(AnalyticsSnapshot).where(
        AnalyticsSnapshot.tenant_id == tenant_id,
        AnalyticsSnapshot.snapshot_type == "MONTHLY",
    )
    if report_date:
        q = q.where(AnalyticsSnapshot.snapshot_date == report_date)
    q = q.order_by(AnalyticsSnapshot.snapshot_date.desc()).limit(1)

    result = await db.execute(q)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(404, "No ADM performance report found")

    return ReportResponse(
        report_type="adm_performance",
        generated_at=record.created_at,
        tenant_id=record.tenant_id,
        period_start=record.snapshot_date - timedelta(days=30),
        period_end=record.snapshot_date,
        data=record.metrics.get("adm_performance", {}),
    )
