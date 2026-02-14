"""modules/integration/service.py — Integration service layer."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import NotFoundError
from modules.integration import batch_processor
from modules.integration.field_mapping import get_default_mapping
from modules.integration.models import IntegrationJob
from modules.tenant.models import Tenant

logger = logging.getLogger(__name__)


async def process_upload(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    content: bytes,
    file_name: str,
    source_system: str,
    user_id: uuid.UUID | None = None,
) -> IntegrationJob:
    """Process a file upload: create job, process file, update job with results."""
    # Get tenant field mapping config
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()

    field_mapping = None
    if tenant and tenant.config:
        integrations = tenant.config.get("integrations", {})
        system_config = integrations.get(source_system, {})
        field_mapping = system_config.get("field_mapping")

    # Create job record
    job = IntegrationJob(
        tenant_id=tenant_id,
        job_type="csv_upload",
        source_system=source_system,
        status="processing",
        file_name=file_name,
        created_by=user_id,
    )
    db.add(job)
    await db.flush()

    # Process the file
    upload_result = await batch_processor.process_file(
        content=content,
        file_name=file_name,
        tenant_id=tenant_id,
        source_system=source_system,
        field_mapping=field_mapping,
        db=db,
    )

    # Update job with results
    job.total_records = upload_result.total_records
    job.processed_records = upload_result.processed
    job.failed_records = upload_result.failed
    job.errors = {"row_errors": [e for e in upload_result.errors]}
    job.status = "completed" if upload_result.failed == 0 else "completed_with_errors"
    await db.flush()

    return job


async def get_job(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
) -> IntegrationJob:
    """Get a single integration job by ID."""
    result = await db.execute(
        select(IntegrationJob).where(
            IntegrationJob.id == job_id,
            IntegrationJob.tenant_id == tenant_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise NotFoundError("IntegrationJob", job_id)
    return job


async def list_jobs(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 50,
    cursor: uuid.UUID | None = None,
    source_system: str | None = None,
    job_type: str | None = None,
) -> tuple[list[IntegrationJob], uuid.UUID | None]:
    """List integration jobs with cursor-based pagination."""
    query = (
        select(IntegrationJob)
        .where(IntegrationJob.tenant_id == tenant_id)
        .order_by(IntegrationJob.created_at.desc(), IntegrationJob.id)
        .limit(limit + 1)
    )
    if source_system:
        query = query.where(IntegrationJob.source_system == source_system)
    if job_type:
        query = query.where(IntegrationJob.job_type == job_type)

    if cursor:
        cursor_job = await db.get(IntegrationJob, cursor)
        if cursor_job:
            query = query.where(
                (IntegrationJob.created_at < cursor_job.created_at)
                | (
                    (IntegrationJob.created_at == cursor_job.created_at)
                    & (IntegrationJob.id > cursor_job.id)
                )
            )

    result = await db.execute(query)
    jobs = list(result.scalars().all())

    next_cursor = None
    if len(jobs) > limit:
        jobs = jobs[:limit]
        next_cursor = jobs[-1].id

    return jobs, next_cursor


def get_field_mapping(tenant: Tenant, source_system: str) -> dict[str, str]:
    """Get effective field mapping: tenant config overrides + defaults."""
    mapping = get_default_mapping(source_system)
    if tenant.config:
        integrations = tenant.config.get("integrations", {})
        system_config = integrations.get(source_system, {})
        tenant_mapping = system_config.get("field_mapping")
        if tenant_mapping:
            mapping.update(tenant_mapping)
    return mapping
