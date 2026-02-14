"""tasks/integration_sync.py — Celery task for scheduled integration sync.

Uses SYNC sessions (psycopg2) — Celery workers are synchronous.
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from config.celery_app import celery_app
from config.database import sync_session_factory
from modules.tenant.models import Tenant

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.integration_sync.sync_external_data")
def sync_external_data() -> dict:
    """Scheduled daily at 00:00 UTC — sync data from external systems.

    Iterates tenants with configured API integrations and triggers sync.
    For now: logs that sync would run (actual API polling is provider-specific).
    """
    with sync_session_factory() as session:
        result = session.execute(
            select(Tenant).where(Tenant.is_active.is_(True))
        )
        tenants = list(result.scalars().all())

        synced = 0
        for tenant in tenants:
            integrations = tenant.config.get("integrations", {})
            if not integrations:
                continue

            for source_system, config in integrations.items():
                if config.get("api_sync_enabled"):
                    logger.info(
                        "Would sync %s for tenant %s (API sync not yet implemented)",
                        source_system,
                        tenant.slug,
                    )
                    synced += 1

        session.commit()
        logger.info("Integration sync check complete: %d systems would sync", synced)
        return {"tenants_checked": len(tenants), "syncs_queued": synced}
