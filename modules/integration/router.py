"""modules/integration/router.py — Integration API endpoints.

- POST /api/v1/integration/upload       — Upload CSV/Excel
- POST /api/v1/integration/sync         — Trigger external data sync
- GET  /api/v1/integration/status       — Integration status overview
- GET  /api/v1/integration/jobs         — List integration jobs
- GET  /api/v1/integration/jobs/{id}    — Get job details
- POST /api/v1/integration/webhooks/{tenant_slug}/{source_system} — External webhook
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_db_no_tenant, require_role
from core.enums import UserRole
from modules.integration import service
from modules.integration.models import IntegrationJob
from modules.integration.schemas import IntegrationJobResponse, SyncRequest, UploadResponse
from modules.integration.webhook_receiver import (
    _get_webhook_secret,
    process_webhook,
    verify_webhook_signature,
)
from modules.tenant.models import Tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/integration", tags=["integration"])


def _to_uuid(value) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


# ─── Upload ───


@router.post("/upload", response_model=IntegrationJobResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    source_system: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.TENANT_ADMIN)),
):
    """Upload a CSV/Excel file for integration processing."""
    tenant_id = _to_uuid(user["tenant_id"])
    user_id = _to_uuid(user["user_id"])

    # Validate source system
    if source_system not in ("pas", "lms", "commission"):
        raise HTTPException(400, f"Invalid source_system: {source_system}. Must be pas, lms, or commission.")

    # Validate file type
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
    if ext not in ("csv", "xlsx", "xls"):
        raise HTTPException(400, "File must be CSV (.csv) or Excel (.xlsx/.xls)")

    content = await file.read()
    if not content:
        raise HTTPException(400, "Uploaded file is empty")

    job = await service.process_upload(
        db=db,
        tenant_id=tenant_id,
        content=content,
        file_name=file.filename or "upload",
        source_system=source_system,
        user_id=user_id,
    )

    return job


# ─── Status ───


@router.get("/status")
async def integration_status(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.TENANT_ADMIN)),
):
    """Get integration status overview for the tenant."""
    from sqlalchemy import func

    tenant_id = _to_uuid(user["tenant_id"])
    result = await db.execute(
        select(
            IntegrationJob.source_system,
            IntegrationJob.status,
            func.count(IntegrationJob.id).label("count"),
            func.max(IntegrationJob.created_at).label("last_run"),
        )
        .where(IntegrationJob.tenant_id == tenant_id)
        .group_by(IntegrationJob.source_system, IntegrationJob.status)
    )
    rows = result.all()

    systems: dict[str, dict] = {}
    for row in rows:
        src = row.source_system
        if src not in systems:
            systems[src] = {"total_jobs": 0, "last_run": None, "statuses": {}}
        systems[src]["statuses"][row.status] = row.count
        systems[src]["total_jobs"] += row.count
        if systems[src]["last_run"] is None or (row.last_run and row.last_run > systems[src]["last_run"]):
            systems[src]["last_run"] = row.last_run

    return {"systems": systems}


# ─── Sync ───


@router.post("/sync", status_code=202)
async def trigger_sync(
    request: SyncRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.TENANT_ADMIN)),
):
    """Trigger an external data sync (placeholder for API-based integrations)."""
    return {
        "status": "accepted",
        "message": f"Sync for {request.source_system} has been queued",
    }


# ─── Jobs ───


@router.get("/jobs")
async def list_jobs(
    limit: int = Query(50, ge=1, le=200),
    cursor: uuid.UUID | None = Query(None),
    source_system: str | None = Query(None),
    job_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.TENANT_ADMIN)),
):
    """List integration jobs with pagination."""
    tenant_id = _to_uuid(user["tenant_id"])
    jobs, next_cursor = await service.list_jobs(
        db, tenant_id, limit=limit, cursor=cursor,
        source_system=source_system, job_type=job_type,
    )
    return {
        "data": [IntegrationJobResponse.model_validate(j) for j in jobs],
        "next_cursor": str(next_cursor) if next_cursor else None,
        "has_more": next_cursor is not None,
    }


@router.get("/jobs/{job_id}", response_model=IntegrationJobResponse)
async def get_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.TENANT_ADMIN)),
):
    """Get integration job details."""
    tenant_id = _to_uuid(user["tenant_id"])
    return await service.get_job(db, tenant_id, job_id)


# ─── Webhook Receiver ───


@router.post("/webhooks/{tenant_slug}/{source_system}")
async def receive_webhook(
    tenant_slug: str,
    source_system: str,
    request: Request,
    db: AsyncSession = Depends(get_db_no_tenant),
):
    """Receive webhook from external system.

    No auth required — uses HMAC-SHA256 signature verification instead.
    """
    # Look up tenant by slug
    result = await db.execute(
        select(Tenant).where(Tenant.slug == tenant_slug, Tenant.is_active.is_(True))
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    # Verify signature
    secret = _get_webhook_secret(tenant, source_system)
    if not secret:
        raise HTTPException(403, "Webhook not configured for this source system")

    body = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")

    if not verify_webhook_signature(body, signature, secret):
        logger.warning(
            "Webhook signature verification failed for tenant=%s source=%s",
            tenant_slug, source_system,
        )
        raise HTTPException(401, "Invalid webhook signature")

    # Parse and process
    payload = await request.json()
    event_type = payload.get("event_type", "")
    data = payload.get("data", {})

    result = await process_webhook(
        tenant=tenant,
        source_system=source_system,
        event_type=event_type,
        data=data,
        db=db,
    )

    await db.commit()
    return result
