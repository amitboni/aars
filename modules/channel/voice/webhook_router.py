"""modules/channel/voice/webhook_router.py — Voice AI webhook endpoint.

POST /api/v1/webhooks/voice/{tenant_slug}
- No auth (webhooks are unauthenticated)
- Signature verified via HMAC-SHA256
- Tenant lookup by slug
- Agent lookup by phone
- NLU extraction from transcript
- Signals emitted via SignalService
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, time, timezone

import zoneinfo
from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db_no_tenant
from config.settings import settings
from core.enums import SignalType
from modules.agent.models import Agent
from modules.channel.voice.nlu import extract_from_transcript
from modules.channel.voice.provider import VoiceCallResult
from modules.signal.schemas import SignalEmit
from modules.signal import service as signal_service
from modules.tenant import service as tenant_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

# TRAI calling hours: 09:00-21:00 IST for voice calls only
_IST = zoneinfo.ZoneInfo("Asia/Kolkata")
_TRAI_START = time(9, 0)
_TRAI_END = time(21, 0)


def is_within_trai_hours() -> bool:
    """Check if current time is within TRAI allowed calling hours (09:00-21:00 IST)."""
    now_ist = datetime.now(_IST).time()
    return _TRAI_START <= now_ist <= _TRAI_END


def _get_voice_provider():
    """Get the configured voice provider instance."""
    if settings.VOICE_PROVIDER == "vibrium":
        from modules.channel.voice.vibrium import VibriumProvider
        return VibriumProvider(
            api_url=settings.VOICE_API_URL,
            api_key=settings.VOICE_API_KEY,
            webhook_secret=settings.VOICE_WEBHOOK_SECRET,
        )
    else:
        from modules.channel.voice.mock import MockVoiceProvider
        return MockVoiceProvider()


@router.post("/voice/{tenant_slug}")
async def voice_webhook(
    tenant_slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db_no_tenant),
    x_webhook_signature: str = Header("", alias="X-Webhook-Signature"),
):
    """Receive voice call results from Vibrium (or mock provider).

    Flow:
    1. Read raw body for signature verification
    2. Verify webhook signature (HMAC-SHA256)
    3. Look up tenant by slug
    4. Parse payload into VoiceCallResult
    5. Look up agent by phone number
    6. Run NLU extraction on transcript
    7. Emit signals: VOICE_CALL_OUTCOME + VOICE_CONVERSATION_ANALYZED
    8. If recording_url present, emit VOICE_CALL_RECORDING_STORED
    """
    body = await request.body()

    # 1. Get provider and verify signature
    provider = _get_voice_provider()
    if not await provider.verify_webhook_signature(body, x_webhook_signature):
        logger.warning("Invalid webhook signature for tenant_slug=%s", tenant_slug)
        return Response(status_code=401, content="Invalid signature")

    # 2. Look up tenant by slug
    tenant = await tenant_service.get_tenant_by_slug(db, tenant_slug)
    if not tenant:
        logger.warning("Voice webhook for unknown tenant slug: %s", tenant_slug)
        return Response(status_code=404, content="Unknown tenant")

    # 3. Parse payload
    payload = await request.json()
    call_result: VoiceCallResult = await provider.handle_callback(payload)

    # 4. Look up agent by phone number
    agent_phone = payload.get("phone_number") or payload.get("agent_phone", "")
    agent_id: uuid.UUID | None = None
    if agent_phone:
        result = await db.execute(
            select(Agent).where(
                Agent.tenant_id == tenant.id,
                Agent.phone == agent_phone,
                Agent.deleted_at.is_(None),
            )
        )
        agent = result.scalar_one_or_none()
        if agent:
            agent_id = agent.id

    if not agent_id:
        logger.warning(
            "Voice webhook: no agent found for phone=%s tenant=%s",
            agent_phone, tenant_slug,
        )

    # 5. Run NLU extraction
    nlu_result = extract_from_transcript(
        transcript=call_result.transcript_text or "",
        provider_sentiment=call_result.sentiment,
        provider_analysis=call_result.analysis,
    )

    # 6. Emit VOICE_CALL_OUTCOME signal
    call_idempotency = f"voice_outcome:{call_result.call_id}"
    outcome_signal = SignalEmit(
        signal_type=SignalType.VOICE_CALL_OUTCOME,
        source="voice_ai",
        agent_id=agent_id,
        channel="voice_ai",
        payload={
            "outcome": call_result.outcome.value,
            "duration_seconds": call_result.duration_seconds,
            "language_detected": call_result.language_detected,
            "call_id": str(call_result.call_id),
        },
        idempotency_key=call_idempotency,
    )
    await signal_service.emit_signal(db, tenant.id, outcome_signal)

    # 7. Emit VOICE_CONVERSATION_ANALYZED signal
    analysis_idempotency = f"voice_analyzed:{call_result.call_id}"
    analyzed_signal = SignalEmit(
        signal_type=SignalType.VOICE_CONVERSATION_ANALYZED,
        source="voice_ai",
        agent_id=agent_id,
        channel="voice_ai",
        payload={
            "call_id": str(call_result.call_id),
            "transcript_summary": call_result.transcript_summary or "",
            "sentiment": nlu_result.sentiment.value if nlu_result.sentiment else "neutral",
            "dormancy_reasons_detected": [r["code"] for r in nlu_result.dormancy_reasons],
            "dormancy_reason_details": nlu_result.dormancy_reasons,
            "product_interests_mentioned": nlu_result.product_interests,
            "competitor_mentions": nlu_result.competitor_mentions,
            "commission_concerns": nlu_result.commission_concerns,
            "adm_relationship_signals": {
                "mentioned_adm": nlu_result.adm_mentioned,
                "adm_sentiment": nlu_result.adm_sentiment.value if nlu_result.adm_sentiment else None,
            },
            "action_items_detected": nlu_result.action_items,
            "reachability_preference": nlu_result.reachability_preference,
            "key_quotes": nlu_result.key_quotes,
            "training_needs": nlu_result.training_needs,
        },
        idempotency_key=analysis_idempotency,
    )
    await signal_service.emit_signal(db, tenant.id, analyzed_signal)

    # 8. Emit VOICE_CALL_RECORDING_STORED if recording URL present
    if call_result.recording_url:
        recording_idempotency = f"voice_recording:{call_result.call_id}"
        recording_signal = SignalEmit(
            signal_type=SignalType.VOICE_CALL_RECORDING_STORED,
            source="voice_ai",
            agent_id=agent_id,
            channel="voice_ai",
            payload={
                "call_id": str(call_result.call_id),
                "recording_url": call_result.recording_url,
                "recording_duration_seconds": call_result.duration_seconds,
            },
            idempotency_key=recording_idempotency,
        )
        await signal_service.emit_signal(db, tenant.id, recording_signal)

    await db.commit()

    logger.info(
        "Voice webhook processed: tenant=%s agent=%s outcome=%s",
        tenant_slug, agent_id, call_result.outcome.value,
    )
    return {"status": "ok", "call_id": str(call_result.call_id)}
