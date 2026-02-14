"""modules/channel/whatsapp/mock.py — Mock WhatsApp provider for testing."""
from __future__ import annotations

import uuid

from modules.channel.whatsapp.provider import (
    WhatsAppDeliveryStatus,
    WhatsAppIncomingMessage,
    WhatsAppMessage,
    WhatsAppProvider,
)


class MockWhatsAppProvider(WhatsAppProvider):
    """Mock provider that records calls for assertions in tests."""

    def __init__(self) -> None:
        self.sent_messages: list[WhatsAppMessage] = []
        self.sent_templates: list[WhatsAppMessage] = []
        self._next_message_id: str | None = None
        self._webhook_responses: list | None = None

    async def send_message(self, message: WhatsAppMessage) -> str:
        self.sent_messages.append(message)
        msg_id = self._next_message_id or f"mock-wamid-{uuid.uuid4().hex[:12]}"
        self._next_message_id = None
        return msg_id

    async def send_template(self, message: WhatsAppMessage) -> str:
        self.sent_templates.append(message)
        msg_id = self._next_message_id or f"mock-wamid-{uuid.uuid4().hex[:12]}"
        self._next_message_id = None
        return msg_id

    async def handle_webhook(self, payload: dict) -> list:
        if self._webhook_responses is not None:
            return self._webhook_responses
        # Default: return empty list
        return []

    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        return True

    # ─── Test helpers ─────────────────────────────────────────────────────

    def set_next_message_id(self, msg_id: str) -> None:
        self._next_message_id = msg_id

    def set_webhook_responses(self, responses: list) -> None:
        self._webhook_responses = responses

    def reset(self) -> None:
        self.sent_messages.clear()
        self.sent_templates.clear()
        self._next_message_id = None
        self._webhook_responses = None
