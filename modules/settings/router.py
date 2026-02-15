"""modules/settings/router.py — Settings management API endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_role
from modules.settings import service
from modules.settings.otp import mask_email
from modules.settings.schemas import (
    ChangeRequestDetailResponse,
    SettingsAuditLogResponse,
    SettingsChangeRequestBody,
    SettingsChangeRequestResponse,
    VerifyOTPBody,
)

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


# ─── Read Settings ──────────────────────────────────────────────────────────


@router.get(
    "",
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def get_all_settings(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get all settings sections with values and metadata."""
    return await service.get_all_settings(db, user["tenant_id"])


@router.get(
    "/audit-log",
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def list_audit_log(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    cursor: uuid.UUID | None = Query(None),
    section: str | None = Query(None),
):
    """List settings audit log with cursor-based pagination."""
    entries, next_cursor = await service.list_audit_log(
        db, user["tenant_id"], limit, cursor, section=section
    )
    return {
        "data": [SettingsAuditLogResponse.model_validate(e) for e in entries],
        "next_cursor": str(next_cursor) if next_cursor else None,
        "has_more": next_cursor is not None,
    }


@router.get(
    "/{section}",
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def get_section_settings(
    section: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get a specific settings section with values and metadata."""
    return await service.get_section_settings(db, user["tenant_id"], section)


# ─── Change Settings (OTP Required) ─────────────────────────────────────────


@router.post(
    "/{section}/request-change",
    response_model=SettingsChangeRequestResponse,
    status_code=201,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def request_settings_change(
    section: str,
    body: SettingsChangeRequestBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Propose settings changes. Triggers OTP to admin email."""
    change_request = await service.request_settings_change(
        db, user["tenant_id"], user["user_id"], section, body.changes
    )
    return SettingsChangeRequestResponse(
        change_request_id=change_request.id,
        otp_sent_to=mask_email(change_request.otp_sent_to),
        expires_at=change_request.otp_expires_at,
        changes_summary=change_request.proposed_values,
    )


@router.post(
    "/verify-otp",
    response_model=SettingsAuditLogResponse,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def verify_otp(
    body: VerifyOTPBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Verify OTP and apply the settings change."""
    audit_log = await service.verify_and_apply(
        db, user["tenant_id"], user["user_id"],
        body.change_request_id, body.otp,
    )
    return SettingsAuditLogResponse.model_validate(audit_log)


@router.post(
    "/{section}/request-change/cancel",
    response_model=ChangeRequestDetailResponse,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def cancel_change_request(
    section: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Cancel a pending change request."""
    change_request_id = body.get("change_request_id")
    if not change_request_id:
        from core.exceptions import ValidationError
        raise ValidationError("change_request_id is required")
    change_request = await service.cancel_change_request(
        db, user["tenant_id"], uuid.UUID(change_request_id)
    )
    return ChangeRequestDetailResponse.model_validate(change_request)
