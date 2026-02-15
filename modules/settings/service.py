"""modules/settings/service.py — Settings CRUD, OTP request/verify, audit trail."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from modules.settings.models import SettingsAuditLog, SettingsChangeRequest
from modules.settings.otp import (
    check_otp_hash,
    generate_otp,
    hash_otp,
    invalidate_otp,
    mask_email,
    send_otp_email,
    store_otp,
    verify_otp as redis_verify_otp,
)
from modules.settings.validators import (
    VALID_SECTIONS,
    get_section_metadata,
    validate_section_changes,
)
from modules.tenant.models import Tenant
from modules.user.models import User


async def get_all_settings(
    db: AsyncSession, tenant_id: uuid.UUID
) -> dict:
    """Get all settings sections with values and field metadata."""
    tenant = await _get_tenant(db, tenant_id)
    config = tenant.config or {}

    result = {}
    for section in VALID_SECTIONS:
        values = config.get(section, {})
        metadata = get_section_metadata(section) or {}
        result[section] = {
            "values": values,
            "metadata": metadata,
        }
    return result


async def get_section_settings(
    db: AsyncSession, tenant_id: uuid.UUID, section: str
) -> dict:
    """Get a single settings section with values and metadata."""
    if section not in VALID_SECTIONS:
        raise NotFoundError("SettingsSection", section)

    tenant = await _get_tenant(db, tenant_id)
    config = tenant.config or {}
    values = config.get(section, {})
    metadata = get_section_metadata(section) or {}

    return {
        "values": values,
        "metadata": metadata,
    }


async def request_settings_change(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    section: str,
    proposed_changes: dict,
) -> SettingsChangeRequest:
    """Create a settings change request and trigger OTP.

    1. Validate section name
    2. Validate proposed values (reject before OTP if invalid)
    3. Load current values
    4. Compute diff — reject if nothing changed
    5. Cancel any existing pending requests for this section
    6. Create SettingsChangeRequest with status=pending_otp
    7. Generate OTP, store in Redis + DB
    8. Log OTP to console
    """
    if section not in VALID_SECTIONS:
        raise NotFoundError("SettingsSection", section)

    tenant = await _get_tenant(db, tenant_id)
    config = tenant.config or {}
    current_values = config.get(section, {})

    # Validate proposed changes
    errors = validate_section_changes(section, proposed_changes, current_values)
    if errors:
        raise ValidationError(
            "; ".join(errors),
            details={"errors": errors},
        )

    # Check if anything actually changed
    if not _has_changes(current_values, proposed_changes, section):
        raise ConflictError(
            "No changes detected — proposed values match current settings",
            details={"section": section},
        )

    # Cancel any existing pending requests for this section+tenant
    await db.execute(
        update(SettingsChangeRequest)
        .where(
            SettingsChangeRequest.tenant_id == tenant_id,
            SettingsChangeRequest.section == section,
            SettingsChangeRequest.status == "pending_otp",
        )
        .values(status="expired")
    )

    # Look up user email
    user = await _get_user(db, user_id)

    # Generate OTP
    otp = generate_otp()
    otp_hashed = hash_otp(otp)

    # Create change request
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    change_request = SettingsChangeRequest(
        tenant_id=tenant_id,
        requested_by=user_id,
        section=section,
        current_values=current_values,
        proposed_values=proposed_changes,
        status="pending_otp",
        otp_hash=otp_hashed,
        otp_attempts=0,
        otp_sent_to=user.email,
        otp_expires_at=expires_at,
    )
    db.add(change_request)
    await db.flush()

    # Store OTP hash in Redis (primary, 10-min TTL)
    await store_otp(change_request.id, otp, ttl_seconds=600)

    # Send OTP (logs to console)
    changes_summary = json.dumps(proposed_changes, indent=2)
    await send_otp_email(
        email=user.email,
        otp=otp,
        section=section,
        changes_summary=changes_summary,
        change_request_id=change_request.id,
    )

    return change_request


async def verify_and_apply(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    change_request_id: uuid.UUID,
    otp: str,
) -> SettingsAuditLog:
    """Verify OTP and apply the settings change.

    1. Load change request, verify belongs to tenant
    2. Check status=pending_otp, not expired, attempts < 3
    3. Increment otp_attempts
    4. Verify OTP (Redis first, fall back to DB hash)
    5. If wrong and attempts >= 3: reject
    6. If correct: merge, apply, create audit log
    """
    change_request = await _get_change_request(db, change_request_id, tenant_id)

    # Check status
    if change_request.status == "applied":
        raise ValidationError(
            "This change request has already been applied",
            details={"status": change_request.status},
        )
    if change_request.status == "rejected":
        raise ValidationError(
            "This change request has been rejected due to too many failed OTP attempts",
            details={"status": change_request.status},
        )
    if change_request.status == "expired":
        raise ValidationError(
            "This change request has been cancelled or expired",
            details={"status": change_request.status},
        )
    if change_request.status != "pending_otp":
        raise ValidationError(
            f"Cannot verify change request in status '{change_request.status}'",
            details={"status": change_request.status},
        )

    # Check expiry
    if datetime.now(timezone.utc) > change_request.otp_expires_at:
        change_request.status = "expired"
        await db.commit()
        raise ValidationError(
            "OTP has expired. Please request a new change.",
            details={"expired_at": change_request.otp_expires_at.isoformat()},
        )

    # Increment attempts
    change_request.otp_attempts += 1

    # Verify OTP — Redis first, fall back to DB hash
    otp_valid = await redis_verify_otp(change_request_id, otp)
    if not otp_valid:
        # Fall back to DB hash
        otp_valid = check_otp_hash(otp, change_request.otp_hash)

    if not otp_valid:
        if change_request.otp_attempts >= 3:
            change_request.status = "rejected"
            await db.commit()
            raise AuthenticationError(
                "Too many failed OTP attempts. Change request rejected. "
                "Please create a new change request."
            )
        await db.commit()
        raise AuthenticationError(
            f"Invalid OTP. {3 - change_request.otp_attempts} attempts remaining."
        )

    # OTP verified — apply the change
    now = datetime.now(timezone.utc)

    # Load tenant and merge
    tenant = await _get_tenant(db, tenant_id)
    config = dict(tenant.config or {})
    section = change_request.section
    current_section = config.get(section, {})

    # Snapshot before change
    previous_values = dict(current_section)

    # Merge proposed into current section
    new_section = _merge_changes(current_section, change_request.proposed_values, section)
    config[section] = new_section
    tenant.config = config

    # Compute changed fields
    changed_fields = list(change_request.proposed_values.keys())

    # Update change request
    change_request.status = "applied"
    change_request.applied_at = now

    # Look up user email for audit
    user = await _get_user(db, user_id)

    # Create audit log
    audit_log = SettingsAuditLog(
        tenant_id=tenant_id,
        change_request_id=change_request_id,
        changed_by=user_id,
        changed_by_email=user.email,
        section=section,
        previous_values=previous_values,
        new_values=new_section,
        changed_fields=changed_fields,
        verified_at=now,
        applied_at=now,
    )
    db.add(audit_log)

    # Invalidate Redis OTP
    await invalidate_otp(change_request_id)

    await db.flush()
    return audit_log


async def cancel_change_request(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    change_request_id: uuid.UUID,
) -> SettingsChangeRequest:
    """Cancel a pending change request."""
    change_request = await _get_change_request(db, change_request_id, tenant_id)

    if change_request.status != "pending_otp":
        raise ValidationError(
            f"Cannot cancel change request in status '{change_request.status}'",
            details={"status": change_request.status},
        )

    change_request.status = "expired"
    await invalidate_otp(change_request_id)
    await db.flush()
    return change_request


async def list_audit_log(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 50,
    cursor: uuid.UUID | None = None,
    section: str | None = None,
) -> tuple[list[SettingsAuditLog], uuid.UUID | None]:
    """List audit log entries with cursor-based pagination."""
    query = (
        select(SettingsAuditLog)
        .where(SettingsAuditLog.tenant_id == tenant_id)
        .order_by(SettingsAuditLog.created_at.desc(), SettingsAuditLog.id)
        .limit(limit + 1)
    )
    if section:
        query = query.where(SettingsAuditLog.section == section)

    if cursor:
        cursor_entry = await db.get(SettingsAuditLog, cursor)
        if cursor_entry:
            query = query.where(
                (SettingsAuditLog.created_at < cursor_entry.created_at)
                | (
                    (SettingsAuditLog.created_at == cursor_entry.created_at)
                    & (SettingsAuditLog.id > cursor_entry.id)
                )
            )

    result = await db.execute(query)
    entries = list(result.scalars().all())

    next_cursor = None
    if len(entries) > limit:
        entries = entries[:limit]
        next_cursor = entries[-1].id

    return entries, next_cursor


# ─── Private helpers ────────────────────────────────────────────────────────


async def _get_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise NotFoundError("Tenant", tenant_id)
    return tenant


async def _get_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User", user_id)
    return user


async def _get_change_request(
    db: AsyncSession, request_id: uuid.UUID, tenant_id: uuid.UUID
) -> SettingsChangeRequest:
    result = await db.execute(
        select(SettingsChangeRequest).where(
            SettingsChangeRequest.id == request_id,
            SettingsChangeRequest.tenant_id == tenant_id,
        )
    )
    cr = result.scalar_one_or_none()
    if not cr:
        raise NotFoundError("SettingsChangeRequest", request_id)
    return cr


def _has_changes(current: dict, proposed: dict, section: str) -> bool:
    """Check if proposed changes differ from current values."""
    for field, value in proposed.items():
        if section == "rate_limits" and isinstance(value, dict):
            current_sub = current.get(field, {})
            for sub_key, sub_val in value.items():
                if current_sub.get(sub_key) != sub_val:
                    return True
        else:
            if current.get(field) != value:
                return True
    return False


def _merge_changes(current: dict, proposed: dict, section: str) -> dict:
    """Deep-merge proposed changes into current section values."""
    merged = dict(current)
    for field, value in proposed.items():
        if section == "rate_limits" and isinstance(value, dict):
            if field not in merged:
                merged[field] = {}
            merged[field] = {**merged[field], **value}
        else:
            merged[field] = value
    return merged
