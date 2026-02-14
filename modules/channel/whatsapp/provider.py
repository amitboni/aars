"""modules/channel/whatsapp/provider.py — Abstract WhatsApp provider interface.

Dataclasses for messages, incoming messages, and delivery statuses.
Abstract WhatsAppProvider class that concrete providers implement.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class WhatsAppMessage:
    message_id: uuid.UUID
    to_phone: str
    template_name: str | None = None
    template_language: str | None = None
    template_params: dict | None = None
    text: str | None = None
    media_url: str | None = None
    media_type: str | None = None  # image, video, document, audio
    buttons: list[dict] | None = None


@dataclass
class WhatsAppIncomingMessage:
    from_phone: str
    message_type: str  # text, button, list_reply, image, video, document, audio, reaction
    text: str | None = None
    button_payload: str | None = None
    media_url: str | None = None


@dataclass
class WhatsAppDeliveryStatus:
    message_id: str
    status: str  # sent, delivered, read, failed
    timestamp: datetime = field(default_factory=lambda: datetime.now())
    error_code: str | None = None
    error_message: str | None = None


class WhatsAppProvider(ABC):
    @abstractmethod
    async def send_message(self, message: WhatsAppMessage) -> str:
        """Send text/interactive/media message. Returns provider message ID."""
        ...

    @abstractmethod
    async def send_template(self, message: WhatsAppMessage) -> str:
        """Send template message. Returns provider message ID."""
        ...

    @abstractmethod
    async def handle_webhook(self, payload: dict) -> list:
        """Parse webhook into list of WhatsAppIncomingMessage or WhatsAppDeliveryStatus."""
        ...

    @abstractmethod
    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature. Returns True if valid."""
        ...
