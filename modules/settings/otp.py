"""modules/settings/otp.py — OTP generation, storage, and verification for settings changes."""
from __future__ import annotations

import random
import uuid

import bcrypt
import structlog

from config.redis import redis_client

logger = structlog.get_logger()


def generate_otp() -> str:
    """Generate a 6-digit numeric OTP."""
    return f"{random.randint(0, 999999):06d}"


def hash_otp(otp: str) -> str:
    """Hash an OTP using bcrypt."""
    return bcrypt.hashpw(otp.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_otp_hash(otp: str, hashed: str) -> bool:
    """Verify an OTP against a bcrypt hash."""
    return bcrypt.checkpw(otp.encode("utf-8"), hashed.encode("utf-8"))


async def store_otp(change_request_id: uuid.UUID, otp: str, ttl_seconds: int = 600) -> None:
    """Store bcrypt hash of OTP in Redis with TTL."""
    key = f"otp:{change_request_id}"
    hashed = hash_otp(otp)
    await redis_client.setex(key, ttl_seconds, hashed)


async def verify_otp(change_request_id: uuid.UUID, otp: str) -> bool:
    """Verify OTP against Redis hash. Returns True if correct."""
    key = f"otp:{change_request_id}"
    stored_hash = await redis_client.get(key)
    if not stored_hash:
        return False
    return check_otp_hash(otp, stored_hash)


async def invalidate_otp(change_request_id: uuid.UUID) -> None:
    """Delete OTP from Redis."""
    key = f"otp:{change_request_id}"
    await redis_client.delete(key)


async def send_otp_email(
    email: str,
    otp: str,
    section: str,
    changes_summary: str,
    change_request_id: uuid.UUID,
) -> None:
    """Send OTP via email. Currently logs to console.

    In production, replace with actual email provider (SES, SendGrid, etc.).
    """
    logger.info(
        "SETTINGS_OTP",
        otp=otp,
        email=email,
        section=section,
        change_request_id=str(change_request_id),
        changes_summary=changes_summary,
    )


def mask_email(email: str) -> str:
    """Mask email for display: 'admin@demo.co' -> 'ad***@demo.co'."""
    if "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if len(local) <= 1:
        masked_local = local + "***"
    else:
        masked_local = local[:2] + "***"
    return f"{masked_local}@{domain}"
