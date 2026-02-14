"""tasks/analytics_aggregation.py — Celery tasks for analytics aggregation.

Uses SYNC sessions (psycopg2) — Celery workers are synchronous.
Scheduled via Celery beat:
- Weekly aggregation: Monday at 04:00 UTC
- Monthly reports: 1st of month at 05:00 UTC
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import select, func

from config.celery_app import celery_app
from config.database import sync_session_factory
from modules.analytics.models import AnalyticsSnapshot, DormancyAnalytics, ReactivationFunnel
from modules.analytics.reports import (
    generate_dormancy_report_sync,
    generate_monthly_snapshot_sync,
    generate_reactivation_funnel_sync,
)
from modules.tenant.models import Tenant

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.analytics_aggregation.weekly_aggregation")
def weekly_aggregation() -> dict:
    """Generate weekly analytics snapshots for all tenants.

    Runs Monday at 04:00 UTC. Uses sync session.
    Computes reactivation funnel and dormancy analytics for the past week.
    """
    today = date.today()
    week_start = today - timedelta(days=7)
    week_end = today - timedelta(days=1)
    generated = 0
    errors = 0

    with sync_session_factory() as session:
        # Get all active tenants
        result = session.execute(
            select(Tenant).where(Tenant.is_active.is_(True))
        )
        tenants = list(result.scalars().all())

        for tenant in tenants:
            try:
                # Idempotency: check if funnel already exists for this period
                existing = session.execute(
                    select(func.count()).select_from(ReactivationFunnel).where(
                        ReactivationFunnel.tenant_id == tenant.id,
                        ReactivationFunnel.period_start == week_start,
                    )
                )
                if existing.scalar() > 0:
                    continue

                generate_reactivation_funnel_sync(session, tenant.id, week_start, week_end)
                generate_dormancy_report_sync(session, tenant.id, today)
                generated += 1
            except Exception:
                logger.exception(
                    "Error generating weekly analytics for tenant %s", tenant.id
                )
                errors += 1

        session.commit()

    logger.info("Weekly analytics generated: %d tenants, errors: %d", generated, errors)
    return {"generated": generated, "errors": errors}


@celery_app.task(name="tasks.analytics_aggregation.monthly_reports")
def monthly_reports() -> dict:
    """Generate monthly analytics reports for all tenants.

    Runs on 1st of each month at 05:00 UTC. Uses sync session.
    Generates full monthly snapshot with dashboard, ADM, and training metrics.
    """
    today = date.today()
    generated = 0
    errors = 0

    with sync_session_factory() as session:
        result = session.execute(
            select(Tenant).where(Tenant.is_active.is_(True))
        )
        tenants = list(result.scalars().all())

        for tenant in tenants:
            try:
                # Idempotency: check if snapshot already exists for this month
                existing = session.execute(
                    select(func.count()).select_from(AnalyticsSnapshot).where(
                        AnalyticsSnapshot.tenant_id == tenant.id,
                        AnalyticsSnapshot.snapshot_date == today,
                        AnalyticsSnapshot.snapshot_type == "MONTHLY",
                    )
                )
                if existing.scalar() > 0:
                    continue

                generate_monthly_snapshot_sync(session, tenant.id, today)

                # Also generate monthly reactivation funnel
                month_start = today.replace(day=1) - timedelta(days=1)
                month_start = month_start.replace(day=1)
                generate_reactivation_funnel_sync(
                    session, tenant.id, month_start, today - timedelta(days=1)
                )

                # And dormancy report
                generate_dormancy_report_sync(session, tenant.id, today)

                generated += 1
            except Exception:
                logger.exception(
                    "Error generating monthly reports for tenant %s", tenant.id
                )
                errors += 1

        session.commit()

    logger.info("Monthly reports generated: %d tenants, errors: %d", generated, errors)
    return {"generated": generated, "errors": errors}
