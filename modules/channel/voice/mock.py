"""modules/channel/voice/mock.py — Mock Voice AI provider for testing."""
from __future__ import annotations

import uuid

from core.enums import ContactOutcome, SentimentLabel
from modules.channel.voice.provider import VoiceCallRequest, VoiceCallResult, VoiceProvider


class MockVoiceProvider(VoiceProvider):
    """Mock provider that returns configurable results. Used in tests and dev."""

    def __init__(self) -> None:
        self._next_result: VoiceCallResult | None = None
        self._calls: list[VoiceCallRequest] = []

    def set_next_result(self, result: VoiceCallResult) -> None:
        """Pre-configure the result returned by the next call."""
        self._next_result = result

    @property
    def calls(self) -> list[VoiceCallRequest]:
        """All calls that were initiated (for test assertions)."""
        return self._calls

    def reset(self) -> None:
        self._next_result = None
        self._calls.clear()

    async def initiate_call(self, request: VoiceCallRequest) -> str:
        self._calls.append(request)
        return f"mock-{request.call_id.hex[:12]}"

    async def get_call_result(self, provider_call_id: str) -> VoiceCallResult | None:
        return self._next_result

    async def handle_callback(self, payload: dict) -> VoiceCallResult:
        if self._next_result:
            return self._next_result

        # Parse fields from payload (like Vibrium adapter does)
        call_id_raw = payload.get("call_id")
        try:
            call_id = uuid.UUID(str(call_id_raw))
        except (ValueError, TypeError):
            call_id = uuid.uuid4()

        outcome_map = {"answered": ContactOutcome.ANSWERED, "completed": ContactOutcome.COMPLETED,
                       "no_answer": ContactOutcome.NOT_ANSWERED, "busy": ContactOutcome.BUSY,
                       "switched_off": ContactOutcome.SWITCHED_OFF}
        raw_outcome = str(payload.get("outcome", "completed")).lower()
        outcome = outcome_map.get(raw_outcome, ContactOutcome.COMPLETED)

        sentiment_map = {"positive": SentimentLabel.POSITIVE, "negative": SentimentLabel.NEGATIVE,
                         "neutral": SentimentLabel.NEUTRAL, "frustrated": SentimentLabel.FRUSTRATED}
        raw_sentiment = str(payload.get("sentiment", "neutral")).lower()
        sentiment = sentiment_map.get(raw_sentiment, SentimentLabel.NEUTRAL)

        return VoiceCallResult(
            call_id=call_id,
            outcome=outcome,
            duration_seconds=int(payload.get("duration_seconds", 120)),
            language_detected=str(payload.get("language", "hi")),
            transcript_text=payload.get("transcript", "Mock transcript"),
            transcript_summary=payload.get("summary", "Mock summary"),
            sentiment=sentiment,
            analysis=payload.get("analysis") or payload,
            recording_url=payload.get("recording_url"),
        )

    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        return True
