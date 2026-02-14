"""modules/channel/whatsapp/meta_cloud.py — Meta Cloud API WhatsApp integration.

Outbound: POST https://graph.facebook.com/{API_VERSION}/{PHONE_NUMBER_ID}/messages
Inbound: Parse webhook payload from Meta (messages + statuses)
Verification: HMAC-SHA256 of payload body using APP_SECRET
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timezone

import httpx

from config.settings import settings
from modules.channel.whatsapp.provider import (
    WhatsAppDeliveryStatus,
    WhatsAppIncomingMessage,
    WhatsAppMessage,
    WhatsAppProvider,
)

logger = logging.getLogger(__name__)


class MetaCloudProvider(WhatsAppProvider):
    """Meta Cloud API (Graph API) WhatsApp Business provider."""

    def __init__(self) -> None:
        self._api_version = settings.META_WHATSAPP_API_VERSION
        self._phone_number_id = settings.META_WHATSAPP_PHONE_NUMBER_ID
        self._access_token = settings.META_WHATSAPP_ACCESS_TOKEN
        self._app_secret = settings.META_WHATSAPP_APP_SECRET
        self._base_url = f"https://graph.facebook.com/{self._api_version}"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    def _messages_url(self) -> str:
        return f"{self._base_url}/{self._phone_number_id}/messages"

    async def send_message(self, message: WhatsAppMessage) -> str:
        """Send text/interactive/media message via Meta Graph API."""
        payload = self._build_message_payload(message)
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self._messages_url(),
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            wamid = data.get("messages", [{}])[0].get("id", "")
            logger.info("Meta Cloud: sent message wamid=%s to=%s", wamid, message.to_phone)
            return wamid

    async def send_template(self, message: WhatsAppMessage) -> str:
        """Send template message via Meta Graph API."""
        components = []
        if message.template_params:
            body_params = [
                {"type": "text", "text": str(v)}
                for v in message.template_params.get("body", [])
            ]
            if body_params:
                components.append({"type": "body", "parameters": body_params})

            button_params = message.template_params.get("buttons", [])
            for i, bp in enumerate(button_params):
                components.append({
                    "type": "button",
                    "sub_type": bp.get("sub_type", "quick_reply"),
                    "index": str(i),
                    "parameters": [{"type": "payload", "payload": bp.get("payload", "")}],
                })

        payload = {
            "messaging_product": "whatsapp",
            "to": message.to_phone.lstrip("+"),
            "type": "template",
            "template": {
                "name": message.template_name,
                "language": {"code": message.template_language or "hi"},
                "components": components,
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self._messages_url(),
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            wamid = data.get("messages", [{}])[0].get("id", "")
            logger.info(
                "Meta Cloud: sent template=%s wamid=%s to=%s",
                message.template_name, wamid, message.to_phone,
            )
            return wamid

    def _build_message_payload(self, message: WhatsAppMessage) -> dict:
        """Build Graph API payload based on message type."""
        to = message.to_phone.lstrip("+")
        base = {"messaging_product": "whatsapp", "to": to}

        # Media message
        if message.media_url and message.media_type:
            media_type = message.media_type
            base["type"] = media_type
            base[media_type] = {"link": message.media_url}
            if message.text and media_type in ("image", "video", "document"):
                base[media_type]["caption"] = message.text
            return base

        # Interactive buttons (max 3)
        if message.buttons:
            buttons = message.buttons[:3]
            base["type"] = "interactive"
            base["interactive"] = {
                "type": "button",
                "body": {"text": message.text or ""},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": btn.get("id", f"btn_{i}"),
                                "title": btn.get("title", f"Option {i+1}")[:20],
                            },
                        }
                        for i, btn in enumerate(buttons)
                    ]
                },
            }
            return base

        # Plain text
        base["type"] = "text"
        base["text"] = {"body": message.text or ""}
        return base

    async def handle_webhook(self, payload: dict) -> list:
        """Parse Meta's webhook format into incoming messages and delivery statuses."""
        results: list = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                # Parse incoming messages
                for msg in value.get("messages", []):
                    incoming = self._parse_incoming_message(msg, value)
                    if incoming:
                        results.append(incoming)

                # Parse delivery/read statuses
                for status in value.get("statuses", []):
                    ds = self._parse_status(status)
                    if ds:
                        results.append(ds)

        return results

    def _parse_incoming_message(
        self, msg: dict, value: dict,
    ) -> WhatsAppIncomingMessage | None:
        """Parse a single incoming message from Meta webhook."""
        msg_type = msg.get("type", "text")
        from_phone = msg.get("from", "")
        if from_phone and not from_phone.startswith("+"):
            from_phone = f"+{from_phone}"

        text = None
        button_payload = None
        media_url = None

        if msg_type == "text":
            text = msg.get("text", {}).get("body")
        elif msg_type == "button":
            button_payload = msg.get("button", {}).get("payload")
            text = msg.get("button", {}).get("text")
        elif msg_type == "interactive":
            interactive = msg.get("interactive", {})
            itype = interactive.get("type")
            if itype == "button_reply":
                button_payload = interactive.get("button_reply", {}).get("id")
                text = interactive.get("button_reply", {}).get("title")
            elif itype == "list_reply":
                button_payload = interactive.get("list_reply", {}).get("id")
                text = interactive.get("list_reply", {}).get("title")
        elif msg_type in ("image", "video", "document", "audio"):
            media_data = msg.get(msg_type, {})
            media_url = media_data.get("url") or media_data.get("id")
        elif msg_type == "reaction":
            text = msg.get("reaction", {}).get("emoji")

        return WhatsAppIncomingMessage(
            from_phone=from_phone,
            message_type=msg_type,
            text=text,
            button_payload=button_payload,
            media_url=media_url,
        )

    def _parse_status(self, status: dict) -> WhatsAppDeliveryStatus | None:
        """Parse a delivery/read status from Meta webhook."""
        status_value = status.get("status", "")
        if status_value not in ("sent", "delivered", "read", "failed"):
            return None

        ts = status.get("timestamp")
        timestamp = (
            datetime.fromtimestamp(int(ts), tz=timezone.utc) if ts else datetime.now(timezone.utc)
        )

        error_code = None
        error_message = None
        errors = status.get("errors", [])
        if errors:
            error_code = str(errors[0].get("code", ""))
            error_message = errors[0].get("title", "")

        return WhatsAppDeliveryStatus(
            message_id=status.get("id", ""),
            status=status_value,
            timestamp=timestamp,
            error_code=error_code,
            error_message=error_message,
        )

    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify X-Hub-Signature-256 using HMAC-SHA256 with APP_SECRET."""
        if not self._app_secret:
            return True  # No secret configured — skip in dev
        expected = hmac.new(
            self._app_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature)
