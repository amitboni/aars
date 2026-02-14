"""modules/channel/voice/vibrium.py — Vibrium Voice AI integration.

Vibrium is webhook-driven:
1. Bots are configured on Vibrium's dashboard
2. Vibrium conducts calls and POSTs results to our webhook
3. We parse the payload into VoiceCallResult and emit signals
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import uuid

from core.enums import ContactOutcome, SentimentLabel
from modules.channel.voice.provider import VoiceCallRequest, VoiceCallResult, VoiceProvider

logger = logging.getLogger(__name__)

# Vibrium outcome → our ContactOutcome mapping
_OUTCOME_MAP: dict[str, ContactOutcome] = {
    "answered": ContactOutcome.ANSWERED,
    "completed": ContactOutcome.COMPLETED,
    "partial": ContactOutcome.PARTIAL,
    "no_answer": ContactOutcome.NOT_ANSWERED,
    "not_answered": ContactOutcome.NOT_ANSWERED,
    "busy": ContactOutcome.BUSY,
    "switched_off": ContactOutcome.SWITCHED_OFF,
    "wrong_number": ContactOutcome.WRONG_NUMBER,
    "failed": ContactOutcome.FAILED_TECHNICAL,
    "error": ContactOutcome.FAILED_TECHNICAL,
}

# Vibrium sentiment → our SentimentLabel mapping
_SENTIMENT_MAP: dict[str, SentimentLabel] = {
    "positive": SentimentLabel.POSITIVE,
    "neutral": SentimentLabel.NEUTRAL,
    "negative": SentimentLabel.NEGATIVE,
    "frustrated": SentimentLabel.FRUSTRATED,
    "interested": SentimentLabel.INTERESTED,
    "confused": SentimentLabel.CONFUSED,
}


class VibriumProvider(VoiceProvider):
    """Vibrium Voice AI provider adapter."""

    def __init__(self, api_url: str, api_key: str, webhook_secret: str) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.webhook_secret = webhook_secret

    async def initiate_call(self, request: VoiceCallRequest) -> str:
        """For Vibrium, calls are typically triggered via their dashboard campaigns.
        Returns a tracking ID. Extend with HTTP call if Vibrium exposes a trigger API."""
        tracking_id = f"vib-{request.call_id.hex[:12]}"
        logger.info("Vibrium call tracking ID generated: %s for agent %s", tracking_id, request.agent_id)
        return tracking_id

    async def get_call_result(self, provider_call_id: str) -> VoiceCallResult | None:
        """For webhook-driven flow, results come via handle_callback.
        This method could poll a local cache if needed."""
        return None

    async def handle_callback(self, payload: dict) -> VoiceCallResult:
        """Parse Vibrium webhook payload into VoiceCallResult.

        Expected payload structure (flexible — adapts to Vibrium's actual format):
        {
            "call_id": "uuid-or-string",
            "phone_number": "+91...",
            "outcome": "answered|no_answer|busy|...",
            "duration_seconds": 120,
            "language": "hi",
            "transcript": "full transcript text",
            "summary": "conversation summary",
            "sentiment": "positive|negative|neutral|...",
            "analysis": { ... provider-specific analysis ... },
            "recording_url": "https://..."
        }
        """
        raw_outcome = str(payload.get("outcome", "failed")).lower().strip()
        outcome = _OUTCOME_MAP.get(raw_outcome, ContactOutcome.FAILED_TECHNICAL)

        raw_sentiment = str(payload.get("sentiment", "")).lower().strip()
        sentiment = _SENTIMENT_MAP.get(raw_sentiment)

        call_id_raw = payload.get("call_id")
        try:
            call_id = uuid.UUID(str(call_id_raw))
        except (ValueError, TypeError):
            call_id = uuid.uuid4()

        return VoiceCallResult(
            call_id=call_id,
            outcome=outcome,
            duration_seconds=int(payload.get("duration_seconds", 0)),
            language_detected=str(payload.get("language", "hi")),
            transcript_text=payload.get("transcript"),
            transcript_summary=payload.get("summary"),
            sentiment=sentiment,
            analysis=payload.get("analysis") or payload,
            recording_url=payload.get("recording_url"),
        )

    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify HMAC-SHA256 signature from Vibrium."""
        if not self.webhook_secret:
            logger.warning("Vibrium webhook secret not configured — skipping verification")
            return True
        expected = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
