"""modules/channel/whatsapp/service.py — High-level WhatsApp sending service.

send_template_to_agent() and send_text_to_agent() with consent/rate checks.
Integrates with ChannelRateLimiter and WhatsApp provider.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from core.enums import ConsentStatus, SignalType
from modules.channel.whatsapp.provider import WhatsAppMessage, WhatsAppProvider
from modules.channel.whatsapp.templates import get_template_buttons, render_template
from modules.signal.schemas import SignalEmit
from modules.signal import service as signal_service

logger = logging.getLogger(__name__)


@dataclass
class SendResult:
    """Result of a send attempt."""
    success: bool
    message_id: str | None = None
    error: str | None = None


def _get_provider() -> WhatsAppProvider:
    """Get the configured WhatsApp provider."""
    if settings.WHATSAPP_PROVIDER == "meta":
        from modules.channel.whatsapp.meta_cloud import MetaCloudProvider
        return MetaCloudProvider()
    else:
        from modules.channel.whatsapp.mock import MockWhatsAppProvider
        return MockWhatsAppProvider()


async def send_template_to_agent(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: uuid.UUID,
    agent_phone: str,
    consent_whatsapp: str,
    template_name: str,
    language: str = "hi",
    template_params: dict | None = None,
    rate_limiter=None,
) -> SendResult:
    """Send a template message to an agent with consent and rate limit checks.

    Args:
        db: Database session for signal emission.
        tenant_id: Tenant UUID.
        agent_id: Agent UUID.
        agent_phone: Agent's phone number.
        consent_whatsapp: Agent's WhatsApp consent status.
        template_name: Name of the template to send.
        language: Template language (default: hi).
        template_params: Parameters to fill in the template.
        rate_limiter: Optional ChannelRateLimiter instance.
    """
    # 1. Check consent
    if consent_whatsapp == ConsentStatus.DENIED or consent_whatsapp == ConsentStatus.REVOKED:
        return SendResult(success=False, error="consent_denied")

    # 2. Check rate limit
    if rate_limiter:
        rate_result = await rate_limiter.check_whatsapp_rate(tenant_id, agent_id)
        if not rate_result.allowed:
            return SendResult(success=False, error="rate_limited")

    # 3. Render template for content summary
    rendered = render_template(template_name, language, template_params)

    # 4. Build and send message
    msg = WhatsAppMessage(
        message_id=uuid.uuid4(),
        to_phone=agent_phone,
        template_name=template_name,
        template_language=language,
        template_params={"body": list((template_params or {}).values())},
    )

    provider = _get_provider()
    try:
        wamid = await provider.send_template(msg)
    except Exception as e:
        logger.error("Failed to send template %s to %s: %s", template_name, agent_phone, e)
        return SendResult(success=False, error=str(e))

    # 5. Record rate limit
    if rate_limiter:
        await rate_limiter.record_whatsapp_message(tenant_id, agent_id)

    # 6. Emit WHATSAPP_MESSAGE_SENT signal
    signal_data = SignalEmit(
        signal_type=SignalType.WHATSAPP_MESSAGE_SENT,
        source="whatsapp_bot",
        agent_id=agent_id,
        channel="whatsapp_bot",
        payload={
            "message_type": "TEMPLATE",
            "template_id": template_name,
            "content_summary": rendered or template_name,
            "purpose": _infer_purpose(template_name),
            "wamid": wamid,
        },
        idempotency_key=f"wa_sent:{wamid}",
    )
    await signal_service.emit_signal(db, tenant_id, signal_data)

    return SendResult(success=True, message_id=wamid)


async def send_text_to_agent(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: uuid.UUID,
    agent_phone: str,
    consent_whatsapp: str,
    text: str,
    buttons: list[dict] | None = None,
    rate_limiter=None,
) -> SendResult:
    """Send a free-form text message to an agent (within 24-hour window).

    Args:
        db: Database session for signal emission.
        tenant_id: Tenant UUID.
        agent_id: Agent UUID.
        agent_phone: Agent's phone number.
        consent_whatsapp: Agent's WhatsApp consent status.
        text: The message text.
        buttons: Optional interactive buttons (max 3).
        rate_limiter: Optional ChannelRateLimiter instance.
    """
    # 1. Check consent
    if consent_whatsapp == ConsentStatus.DENIED or consent_whatsapp == ConsentStatus.REVOKED:
        return SendResult(success=False, error="consent_denied")

    # 2. Check rate limit
    if rate_limiter:
        rate_result = await rate_limiter.check_whatsapp_rate(tenant_id, agent_id)
        if not rate_result.allowed:
            return SendResult(success=False, error="rate_limited")

    # 3. Build and send message
    msg = WhatsAppMessage(
        message_id=uuid.uuid4(),
        to_phone=agent_phone,
        text=text,
        buttons=buttons,
    )

    provider = _get_provider()
    try:
        wamid = await provider.send_message(msg)
    except Exception as e:
        logger.error("Failed to send text to %s: %s", agent_phone, e)
        return SendResult(success=False, error=str(e))

    # 4. Record rate limit
    if rate_limiter:
        await rate_limiter.record_whatsapp_message(tenant_id, agent_id)

    # 5. Emit signal
    msg_type = "INTERACTIVE" if buttons else "TEXT"
    signal_data = SignalEmit(
        signal_type=SignalType.WHATSAPP_MESSAGE_SENT,
        source="whatsapp_bot",
        agent_id=agent_id,
        channel="whatsapp_bot",
        payload={
            "message_type": msg_type,
            "content_summary": text[:200],
            "purpose": "INFO",
            "wamid": wamid,
        },
        idempotency_key=f"wa_sent:{wamid}",
    )
    await signal_service.emit_signal(db, tenant_id, signal_data)

    return SendResult(success=True, message_id=wamid)


def _infer_purpose(template_name: str) -> str:
    """Infer the purpose of a message from the template name."""
    if "training" in template_name:
        return "TRAINING"
    if "checkin" in template_name:
        return "NUDGE"
    if "reminder" in template_name or "expiry" in template_name:
        return "REMINDER"
    if "congratulation" in template_name or "sale" in template_name:
        return "CONGRATULATION"
    if "welcome" in template_name:
        return "INFO"
    return "INFO"
