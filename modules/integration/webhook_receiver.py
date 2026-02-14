"""modules/integration/webhook_receiver.py — Generic webhook handler.

Receives POST from external systems with HMAC-SHA256 signature verification.
Parses payload, routes to appropriate adapter, emits signals.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from modules.integration.commission_adapter import CommissionAdapter
from modules.integration.lms_adapter import LMSLicenseAdapter, LMSTrainingAdapter
from modules.integration.pas_adapter import PASPolicyAdapter
from modules.signal import service as signal_service
from modules.tenant.models import Tenant

logger = logging.getLogger(__name__)


def verify_webhook_signature(
    payload_body: bytes,
    signature: str,
    secret: str,
) -> bool:
    """Verify HMAC-SHA256 signature of webhook payload.

    Expected signature format: sha256=<hex_digest>
    """
    if not signature or not secret:
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()

    # Support both "sha256=<hex>" and raw "<hex>" formats
    sig_value = signature.removeprefix("sha256=")

    return hmac.compare_digest(expected, sig_value)


def _get_webhook_secret(tenant: Tenant, source_system: str) -> str | None:
    """Extract webhook secret from tenant config."""
    integrations = tenant.config.get("integrations", {})
    system_config = integrations.get(source_system, {})
    return system_config.get("webhook_secret")


def _get_adapter_for_event(source_system: str, event_type: str):
    """Return appropriate adapter based on source system and event type."""
    mapping = {
        "pas": {
            "policy_sold": PASPolicyAdapter(),
        },
        "lms": {
            "training_completed": LMSTrainingAdapter(),
            "license_changed": LMSLicenseAdapter(),
        },
        "commission": {
            "commission_credited": CommissionAdapter(),
        },
    }
    system_adapters = mapping.get(source_system, {})
    return system_adapters.get(event_type)


async def process_webhook(
    tenant: Tenant,
    source_system: str,
    event_type: str,
    data: dict,
    db: AsyncSession,
) -> dict:
    """Process an incoming webhook event.

    Returns a summary dict with processing results.
    """
    adapter = _get_adapter_for_event(source_system, event_type)
    if adapter is None:
        logger.warning(
            "No adapter for webhook %s/%s from tenant %s",
            source_system, event_type, tenant.id,
        )
        return {"status": "ignored", "reason": f"Unknown event type: {event_type}"}

    # Validate
    is_valid, errors = adapter.validate_row(data)
    if not is_valid:
        return {"status": "validation_failed", "errors": errors}

    # Process
    signals = await adapter.process_row(data, tenant.id, db)

    emitted = 0
    duplicates = 0
    for signal_data in signals:
        _, created = await signal_service.emit_signal(db, tenant.id, signal_data)
        if created:
            emitted += 1
        else:
            duplicates += 1

    return {
        "status": "processed",
        "signals_emitted": emitted,
        "duplicates_skipped": duplicates,
    }
