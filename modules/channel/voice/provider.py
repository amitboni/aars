"""modules/channel/voice/provider.py — Abstract Voice AI provider interface."""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from core.enums import ContactOutcome, SentimentLabel


@dataclass
class VoiceCallRequest:
    call_id: uuid.UUID
    tenant_id: uuid.UUID
    agent_id: uuid.UUID
    agent_phone: str
    caller_id: str
    language: str
    conversation_guide: str
    context: dict = field(default_factory=dict)
    max_duration_seconds: int = 300
    persona_name: str = "Priya"


@dataclass
class VoiceCallResult:
    call_id: uuid.UUID
    outcome: ContactOutcome
    duration_seconds: int
    language_detected: str
    transcript_text: str | None = None
    transcript_summary: str | None = None
    sentiment: SentimentLabel | None = None
    analysis: dict | None = None
    recording_url: str | None = None


class VoiceProvider(ABC):
    @abstractmethod
    async def initiate_call(self, request: VoiceCallRequest) -> str:
        """Trigger a call. Returns provider's call ID."""
        ...

    @abstractmethod
    async def get_call_result(self, provider_call_id: str) -> VoiceCallResult | None:
        """Poll for call result. For webhook-driven providers,
        this checks our local cache of received webhook results."""
        ...

    @abstractmethod
    async def handle_callback(self, payload: dict) -> VoiceCallResult:
        """Parse webhook payload from provider into VoiceCallResult."""
        ...

    @abstractmethod
    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify HMAC-SHA256 webhook signature from provider."""
        ...
