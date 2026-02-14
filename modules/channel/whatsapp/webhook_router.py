"""modules/channel/whatsapp/webhook_router.py — WhatsApp webhook endpoints.

POST /api/v1/webhooks/whatsapp/{tenant_slug}
- Verify X-Hub-Signature-256 via HMAC-SHA256
- Parse incoming messages and delivery statuses
- Classify intent, route to bot/training handlers
- Emit signals via SignalService

GET /api/v1/webhooks/whatsapp/{tenant_slug}
- Meta webhook verification (hub.mode=subscribe)
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db_no_tenant
from config.settings import settings
from core.enums import ConsentStatus, SignalType
from modules.agent.models import Agent
from modules.channel.whatsapp import bot, training
from modules.channel.whatsapp.provider import (
    WhatsAppDeliveryStatus,
    WhatsAppIncomingMessage,
)
from modules.signal.schemas import SignalEmit
from modules.signal import service as signal_service
from modules.tenant import service as tenant_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


def _get_whatsapp_provider():
    """Get the configured WhatsApp provider for signature verification."""
    if settings.WHATSAPP_PROVIDER == "meta":
        from modules.channel.whatsapp.meta_cloud import MetaCloudProvider
        return MetaCloudProvider()
    else:
        from modules.channel.whatsapp.mock import MockWhatsAppProvider
        return MockWhatsAppProvider()


def _get_webhook_parser():
    """Get the Meta Cloud provider for parsing webhook payloads.

    Webhooks always arrive in Meta's format regardless of the configured
    provider, so we always use MetaCloudProvider for parsing.
    """
    from modules.channel.whatsapp.meta_cloud import MetaCloudProvider
    return MetaCloudProvider()


@router.get("/whatsapp/{tenant_slug}")
async def whatsapp_verify(
    tenant_slug: str,
    hub_mode: str = Query("", alias="hub.mode"),
    hub_verify_token: str = Query("", alias="hub.verify_token"),
    hub_challenge: str = Query("", alias="hub.challenge"),
) -> Response:
    """Meta webhook verification endpoint.

    Meta sends a GET request when setting up a webhook subscription.
    We respond with hub.challenge if the verify token matches.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.META_WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified for tenant_slug=%s", tenant_slug)
        return Response(content=hub_challenge, media_type="text/plain")

    logger.warning(
        "WhatsApp webhook verification failed: tenant=%s mode=%s",
        tenant_slug, hub_mode,
    )
    return Response(status_code=403, content="Verification failed")


@router.post("/whatsapp/{tenant_slug}")
async def whatsapp_webhook(
    tenant_slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db_no_tenant),
    x_hub_signature_256: str = Header("", alias="X-Hub-Signature-256"),
):
    """Receive WhatsApp messages and statuses from Meta Cloud API.

    Flow:
    1. Read raw body for signature verification
    2. Verify X-Hub-Signature-256 (HMAC-SHA256)
    3. Look up tenant by slug
    4. Parse payload into messages and statuses
    5. For each incoming message:
       a. Look up agent by phone
       b. Classify intent
       c. Handle via bot/training
       d. Emit WHATSAPP_AGENT_REPLIED signal
    6. For each delivery status:
       a. Emit appropriate signal (delivered/read/failed)
    """
    body = await request.body()

    # 1. Verify signature
    provider = _get_whatsapp_provider()
    if not await provider.verify_webhook_signature(body, x_hub_signature_256):
        logger.warning("Invalid WhatsApp webhook signature for tenant_slug=%s", tenant_slug)
        return Response(status_code=401, content="Invalid signature")

    # 2. Look up tenant
    tenant = await tenant_service.get_tenant_by_slug(db, tenant_slug)
    if not tenant:
        logger.warning("WhatsApp webhook for unknown tenant slug: %s", tenant_slug)
        return Response(status_code=404, content="Unknown tenant")

    # 3. Parse payload (always use MetaCloudProvider for parsing)
    payload = await request.json()
    parser = _get_webhook_parser()
    results = await parser.handle_webhook(payload)

    processed_count = 0

    for item in results:
        if isinstance(item, WhatsAppIncomingMessage):
            await _handle_incoming_message(db, tenant.id, item)
            processed_count += 1
        elif isinstance(item, WhatsAppDeliveryStatus):
            await _handle_delivery_status(db, tenant.id, item)
            processed_count += 1

    await db.commit()

    logger.info(
        "WhatsApp webhook processed: tenant=%s items=%d",
        tenant_slug, processed_count,
    )
    return {"status": "ok", "processed": processed_count}


async def _handle_incoming_message(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    message: WhatsAppIncomingMessage,
) -> None:
    """Handle a single incoming WhatsApp message from an agent."""
    # Look up agent by phone
    agent = await _lookup_agent(db, tenant_id, message.from_phone)
    agent_id = agent.id if agent else None
    agent_name = agent.full_name if agent else ""
    adm_name = ""

    # Look up ADM name if agent has one assigned
    if agent and agent.assigned_adm_id:
        adm_result = await db.execute(
            select(Agent).where(
                Agent.id == agent.assigned_adm_id,
                Agent.tenant_id == tenant_id,
            )
        )
        adm = adm_result.scalar_one_or_none()
        if adm:
            adm_name = adm.full_name

    # Check if agent has active quiz
    active_quiz = False
    if agent:
        active_quiz = training.has_active_quiz(tenant_id, agent.id)

    # Check for quiz button responses
    if message.button_payload and agent:
        parsed = training.parse_quiz_button_payload(message.button_payload)
        if parsed:
            _module_id, _q_index, answer_index = parsed
            quiz_result = training.process_quiz_answer(tenant_id, agent.id, answer_index)
            # Emit training interaction signal if quiz completed
            if quiz_result.is_complete:
                await _emit_training_signal(
                    db, tenant_id, agent.id, _module_id,
                    quiz_result.score_percent, quiz_result.total_questions,
                )
            # The response text would be sent by service.py
            logger.info(
                "Quiz answer processed: agent=%s module=%s complete=%s",
                agent_id, _module_id, quiz_result.is_complete,
            )
            return

    # Classify intent and get response
    intent = bot.classify_intent(message)
    response = bot.handle_message(
        message,
        agent_name=agent_name,
        adm_name=adm_name,
        active_quiz=active_quiz,
    )

    # Handle STOP opt-out
    if response.emit_consent_revoked and agent:
        await _emit_consent_signal(db, tenant_id, agent.id, ConsentStatus.REVOKED)

    # Emit WHATSAPP_AGENT_REPLIED signal
    reply_type = _classify_reply_type(message)
    idempotency_key = f"wa_reply:{message.from_phone}:{hash(message.text or message.button_payload or '')}"

    signal_data = SignalEmit(
        signal_type=SignalType.WHATSAPP_AGENT_REPLIED,
        source="whatsapp_bot",
        agent_id=agent_id,
        channel="whatsapp_bot",
        payload={
            "reply_type": reply_type,
            "reply_content": message.text or message.button_payload or "",
            "intent_detected": intent,
            "from_phone": message.from_phone,
        },
        idempotency_key=idempotency_key,
    )
    await signal_service.emit_signal(db, tenant_id, signal_data)

    # Emit ADM escalation signal if needed
    if response.escalate_to_adm and agent and agent.assigned_adm_id:
        adm_signal = SignalEmit(
            signal_type=SignalType.ADM_NUDGE_RECEIVED,
            source="whatsapp_bot",
            agent_id=agent_id,
            adm_id=agent.assigned_adm_id,
            channel="whatsapp_bot",
            payload={
                "nudge_type": "AGENT_ALERT",
                "content_summary": response.escalation_reason or "",
                "agent_phone": message.from_phone,
            },
        )
        await signal_service.emit_signal(db, tenant_id, adm_signal)

    logger.info(
        "WhatsApp message handled: agent=%s intent=%s escalate=%s",
        agent_id, intent, response.escalate_to_adm,
    )


async def _handle_delivery_status(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    status: WhatsAppDeliveryStatus,
) -> None:
    """Handle a delivery status update (sent/delivered/read/failed)."""
    signal_type_map = {
        "sent": SignalType.WHATSAPP_MESSAGE_SENT,
        "delivered": SignalType.WHATSAPP_MESSAGE_DELIVERED,
        "read": SignalType.WHATSAPP_MESSAGE_READ,
    }

    signal_type = signal_type_map.get(status.status)
    if not signal_type:
        if status.status == "failed":
            logger.warning(
                "WhatsApp message failed: msg_id=%s error=%s/%s",
                status.message_id, status.error_code, status.error_message,
            )
        return

    idempotency_key = f"wa_status:{status.message_id}:{status.status}"
    signal_data = SignalEmit(
        signal_type=signal_type,
        source="whatsapp_bot",
        channel="whatsapp_bot",
        payload={
            "message_id": status.message_id,
            "status": status.status,
            "timestamp": status.timestamp.isoformat() if status.timestamp else None,
            "error_code": status.error_code,
            "error_message": status.error_message,
        },
        idempotency_key=idempotency_key,
    )
    await signal_service.emit_signal(db, tenant_id, signal_data)


async def _lookup_agent(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    phone: str,
) -> Agent | None:
    """Look up an agent by phone number within a tenant."""
    # Normalize phone: ensure +prefix
    normalized = phone if phone.startswith("+") else f"+{phone}"
    result = await db.execute(
        select(Agent).where(
            Agent.tenant_id == tenant_id,
            Agent.phone == normalized,
            Agent.deleted_at.is_(None),
        )
    )
    agent = result.scalar_one_or_none()
    if not agent:
        # Try without + prefix
        result = await db.execute(
            select(Agent).where(
                Agent.tenant_id == tenant_id,
                Agent.phone == phone.lstrip("+"),
                Agent.deleted_at.is_(None),
            )
        )
        agent = result.scalar_one_or_none()
    return agent


async def _emit_consent_signal(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: uuid.UUID,
    status: str,
) -> None:
    """Emit a CONSENT_CHANGED signal."""
    signal_data = SignalEmit(
        signal_type=SignalType.CONSENT_CHANGED,
        source="whatsapp_bot",
        agent_id=agent_id,
        channel="whatsapp_bot",
        payload={
            "consent_type": "whatsapp",
            "new_status": status,
            "method": "WHATSAPP_REPLY",
        },
    )
    await signal_service.emit_signal(db, tenant_id, signal_data)


async def _emit_training_signal(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: uuid.UUID,
    module_id: str,
    score_percent: float,
    total_questions: int,
) -> None:
    """Emit a WHATSAPP_TRAINING_INTERACTION signal for a completed quiz."""
    signal_data = SignalEmit(
        signal_type=SignalType.WHATSAPP_TRAINING_INTERACTION,
        source="whatsapp_bot",
        agent_id=agent_id,
        channel="whatsapp_bot",
        payload={
            "module_id": module_id,
            "interaction_type": "QUIZ_COMPLETED",
            "quiz_score": score_percent,
            "quiz_max_score": 100.0,
            "total_questions": total_questions,
        },
        idempotency_key=f"wa_quiz:{agent_id}:{module_id}",
    )
    await signal_service.emit_signal(db, tenant_id, signal_data)


def _classify_reply_type(message: WhatsAppIncomingMessage) -> str:
    """Map message type to reply type enum."""
    if message.message_type == "text":
        return "TEXT"
    if message.message_type in ("button", "interactive"):
        return "BUTTON_CLICK"
    if message.message_type == "audio":
        return "VOICE_NOTE"
    if message.message_type in ("image", "video", "document"):
        return "MEDIA"
    return "TEXT"
