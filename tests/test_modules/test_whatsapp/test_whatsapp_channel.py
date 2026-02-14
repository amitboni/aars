"""Tests for WhatsApp Channel (Slice 3 — Meta Cloud API).

Covers: provider interface, mock provider, Meta Cloud adapter, webhook endpoints,
bot intent classification, message handling, templates, training quiz flow,
rate limiting integration, sending service, tenant isolation, and regression.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from api.app import create_app
from config.database import sync_engine
from core.enums import ConsentStatus, SignalType


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def wa_tenant() -> dict:
    """Create a test tenant for WhatsApp tests."""
    tenant_id = uuid.uuid4()
    slug = f"wa-{tenant_id.hex[:8]}"
    with sync_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO tenants (id, name, slug, subscription_tier, is_active, config) "
                "VALUES (:id, :name, :slug, 'trial', true, '{}'::jsonb)"
            ),
            {"id": str(tenant_id), "name": f"WA Test {slug}", "slug": slug},
        )
    yield {"id": tenant_id, "slug": slug}
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM signals WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM agents WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM users WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM tenants WHERE id = :tid"), {"tid": str(tenant_id)})


@pytest.fixture
def wa_agent(wa_tenant: dict) -> dict:
    """Create a test agent with a known phone number."""
    agent_id = uuid.uuid4()
    adm_id = uuid.uuid4()
    phone = "+919876543210"
    with sync_engine.begin() as conn:
        # Create ADM agent (to test ADM lookup)
        conn.execute(
            text(
                "INSERT INTO agents (id, tenant_id, agent_code, full_name, phone, lifecycle_state) "
                "VALUES (:id, :tid, :code, :name, :phone, 'active')"
            ),
            {
                "id": str(adm_id),
                "tid": str(wa_tenant["id"]),
                "code": f"ADM-{adm_id.hex[:8]}",
                "name": "Test ADM Manager",
                "phone": "+919000000001",
            },
        )
        # Create agent
        conn.execute(
            text(
                "INSERT INTO agents (id, tenant_id, agent_code, full_name, phone, "
                "lifecycle_state, assigned_adm_id, consent_whatsapp, preferred_language) "
                "VALUES (:id, :tid, :code, :name, :phone, 'dormant', :adm_id, 'granted', 'hi')"
            ),
            {
                "id": str(agent_id),
                "tid": str(wa_tenant["id"]),
                "code": f"WA-{agent_id.hex[:8]}",
                "name": "Rahul Sharma",
                "phone": phone,
                "adm_id": str(adm_id),
            },
        )
    yield {
        "id": agent_id,
        "phone": phone,
        "name": "Rahul Sharma",
        "tenant_id": wa_tenant["id"],
        "adm_id": adm_id,
    }
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM signals WHERE agent_id = :aid"), {"aid": str(agent_id)})
        conn.execute(text("DELETE FROM signals WHERE agent_id = :aid"), {"aid": str(adm_id)})
        conn.execute(text("DELETE FROM agents WHERE id = :aid"), {"aid": str(agent_id)})
        conn.execute(text("DELETE FROM agents WHERE id = :aid"), {"aid": str(adm_id)})


def _make_meta_webhook_payload(
    from_phone: str = "919876543210",
    message_type: str = "text",
    text_body: str = "Hello",
    button_id: str | None = None,
    button_title: str | None = None,
) -> dict:
    """Build a Meta-format webhook payload for testing."""
    messages = []
    if message_type == "text":
        messages.append({
            "from": from_phone,
            "id": f"wamid.{uuid.uuid4().hex[:20]}",
            "timestamp": str(int(datetime.now(timezone.utc).timestamp())),
            "type": "text",
            "text": {"body": text_body},
        })
    elif message_type == "button":
        messages.append({
            "from": from_phone,
            "id": f"wamid.{uuid.uuid4().hex[:20]}",
            "timestamp": str(int(datetime.now(timezone.utc).timestamp())),
            "type": "button",
            "button": {"payload": button_id or "btn_0", "text": button_title or "Option 1"},
        })
    elif message_type == "interactive":
        messages.append({
            "from": from_phone,
            "id": f"wamid.{uuid.uuid4().hex[:20]}",
            "timestamp": str(int(datetime.now(timezone.utc).timestamp())),
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": button_id or "btn_0", "title": button_title or "Option 1"},
            },
        })
    elif message_type == "image":
        messages.append({
            "from": from_phone,
            "id": f"wamid.{uuid.uuid4().hex[:20]}",
            "timestamp": str(int(datetime.now(timezone.utc).timestamp())),
            "type": "image",
            "image": {"id": "img_123", "mime_type": "image/jpeg"},
        })
    elif message_type == "audio":
        messages.append({
            "from": from_phone,
            "id": f"wamid.{uuid.uuid4().hex[:20]}",
            "timestamp": str(int(datetime.now(timezone.utc).timestamp())),
            "type": "audio",
            "audio": {"id": "audio_123", "mime_type": "audio/ogg"},
        })

    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "BIZ_ACCOUNT_ID",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"phone_number_id": "PHONE_ID"},
                    "messages": messages,
                    "contacts": [{"profile": {"name": "Test"}, "wa_id": from_phone}],
                },
                "field": "messages",
            }],
        }],
    }


def _make_status_webhook_payload(
    message_id: str = "wamid.test123",
    status: str = "delivered",
) -> dict:
    """Build a Meta-format status webhook payload."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "BIZ_ACCOUNT_ID",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"phone_number_id": "PHONE_ID"},
                    "statuses": [{
                        "id": message_id,
                        "status": status,
                        "timestamp": str(int(datetime.now(timezone.utc).timestamp())),
                        "recipient_id": "919876543210",
                    }],
                },
                "field": "messages",
            }],
        }],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Provider Interface Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestMockWhatsAppProvider:
    async def test_send_message(self):
        from modules.channel.whatsapp.mock import MockWhatsAppProvider
        from modules.channel.whatsapp.provider import WhatsAppMessage

        provider = MockWhatsAppProvider()
        msg = WhatsAppMessage(message_id=uuid.uuid4(), to_phone="+919876543210", text="Hello")
        wamid = await provider.send_message(msg)
        assert wamid.startswith("mock-wamid-")
        assert len(provider.sent_messages) == 1
        assert provider.sent_messages[0].text == "Hello"

    async def test_send_template(self):
        from modules.channel.whatsapp.mock import MockWhatsAppProvider
        from modules.channel.whatsapp.provider import WhatsAppMessage

        provider = MockWhatsAppProvider()
        msg = WhatsAppMessage(
            message_id=uuid.uuid4(),
            to_phone="+919876543210",
            template_name="welcome_new_agent",
            template_language="hi",
        )
        wamid = await provider.send_template(msg)
        assert wamid.startswith("mock-wamid-")
        assert len(provider.sent_templates) == 1

    async def test_set_next_message_id(self):
        from modules.channel.whatsapp.mock import MockWhatsAppProvider
        from modules.channel.whatsapp.provider import WhatsAppMessage

        provider = MockWhatsAppProvider()
        provider.set_next_message_id("custom-id-123")
        msg = WhatsAppMessage(message_id=uuid.uuid4(), to_phone="+919876543210", text="Test")
        wamid = await provider.send_message(msg)
        assert wamid == "custom-id-123"

    async def test_handle_webhook_default(self):
        from modules.channel.whatsapp.mock import MockWhatsAppProvider

        provider = MockWhatsAppProvider()
        result = await provider.handle_webhook({"test": True})
        assert result == []

    async def test_set_webhook_responses(self):
        from modules.channel.whatsapp.mock import MockWhatsAppProvider

        provider = MockWhatsAppProvider()
        provider.set_webhook_responses(["resp1", "resp2"])
        result = await provider.handle_webhook({})
        assert result == ["resp1", "resp2"]

    async def test_verify_signature_always_true(self):
        from modules.channel.whatsapp.mock import MockWhatsAppProvider

        provider = MockWhatsAppProvider()
        assert await provider.verify_webhook_signature(b"anything", "any") is True

    async def test_reset(self):
        from modules.channel.whatsapp.mock import MockWhatsAppProvider
        from modules.channel.whatsapp.provider import WhatsAppMessage

        provider = MockWhatsAppProvider()
        await provider.send_message(
            WhatsAppMessage(message_id=uuid.uuid4(), to_phone="+91", text="x")
        )
        assert len(provider.sent_messages) == 1
        provider.reset()
        assert len(provider.sent_messages) == 0


class TestMetaCloudProvider:
    async def test_handle_webhook_text_message(self):
        from modules.channel.whatsapp.meta_cloud import MetaCloudProvider

        provider = MetaCloudProvider()
        payload = _make_meta_webhook_payload(message_type="text", text_body="Hi there")
        results = await provider.handle_webhook(payload)
        assert len(results) == 1
        msg = results[0]
        assert msg.from_phone == "+919876543210"
        assert msg.text == "Hi there"
        assert msg.message_type == "text"

    async def test_handle_webhook_button_message(self):
        from modules.channel.whatsapp.meta_cloud import MetaCloudProvider

        provider = MetaCloudProvider()
        payload = _make_meta_webhook_payload(
            message_type="button", button_id="pay_btn", button_title="Pay Now"
        )
        results = await provider.handle_webhook(payload)
        assert len(results) == 1
        msg = results[0]
        assert msg.button_payload == "pay_btn"
        assert msg.text == "Pay Now"

    async def test_handle_webhook_interactive_button_reply(self):
        from modules.channel.whatsapp.meta_cloud import MetaCloudProvider

        provider = MetaCloudProvider()
        payload = _make_meta_webhook_payload(
            message_type="interactive", button_id="training_chahiye", button_title="Training chahiye"
        )
        results = await provider.handle_webhook(payload)
        assert len(results) == 1
        msg = results[0]
        assert msg.button_payload == "training_chahiye"

    async def test_handle_webhook_image_message(self):
        from modules.channel.whatsapp.meta_cloud import MetaCloudProvider

        provider = MetaCloudProvider()
        payload = _make_meta_webhook_payload(message_type="image")
        results = await provider.handle_webhook(payload)
        assert len(results) == 1
        assert results[0].message_type == "image"

    async def test_handle_webhook_delivery_status(self):
        from modules.channel.whatsapp.meta_cloud import MetaCloudProvider
        from modules.channel.whatsapp.provider import WhatsAppDeliveryStatus

        provider = MetaCloudProvider()
        payload = _make_status_webhook_payload(status="delivered")
        results = await provider.handle_webhook(payload)
        assert len(results) == 1
        assert isinstance(results[0], WhatsAppDeliveryStatus)
        assert results[0].status == "delivered"

    async def test_handle_webhook_read_status(self):
        from modules.channel.whatsapp.meta_cloud import MetaCloudProvider
        from modules.channel.whatsapp.provider import WhatsAppDeliveryStatus

        provider = MetaCloudProvider()
        payload = _make_status_webhook_payload(status="read")
        results = await provider.handle_webhook(payload)
        assert len(results) == 1
        assert results[0].status == "read"

    async def test_handle_webhook_empty_payload(self):
        from modules.channel.whatsapp.meta_cloud import MetaCloudProvider

        provider = MetaCloudProvider()
        results = await provider.handle_webhook({})
        assert results == []

    async def test_verify_signature_valid(self):
        from modules.channel.whatsapp.meta_cloud import MetaCloudProvider

        with patch("modules.channel.whatsapp.meta_cloud.settings") as mock_settings:
            mock_settings.META_WHATSAPP_APP_SECRET = "test-secret-123"
            mock_settings.META_WHATSAPP_API_VERSION = "v21.0"
            mock_settings.META_WHATSAPP_PHONE_NUMBER_ID = "123"
            mock_settings.META_WHATSAPP_ACCESS_TOKEN = "token"
            provider = MetaCloudProvider()

        payload = b'{"test": true}'
        expected = hmac.new(b"test-secret-123", payload, hashlib.sha256).hexdigest()
        sig = f"sha256={expected}"
        assert await provider.verify_webhook_signature(payload, sig) is True

    async def test_verify_signature_invalid(self):
        from modules.channel.whatsapp.meta_cloud import MetaCloudProvider

        with patch("modules.channel.whatsapp.meta_cloud.settings") as mock_settings:
            mock_settings.META_WHATSAPP_APP_SECRET = "test-secret-123"
            mock_settings.META_WHATSAPP_API_VERSION = "v21.0"
            mock_settings.META_WHATSAPP_PHONE_NUMBER_ID = "123"
            mock_settings.META_WHATSAPP_ACCESS_TOKEN = "token"
            provider = MetaCloudProvider()

        assert await provider.verify_webhook_signature(b"data", "sha256=wrong") is False

    async def test_verify_signature_no_secret(self):
        from modules.channel.whatsapp.meta_cloud import MetaCloudProvider

        with patch("modules.channel.whatsapp.meta_cloud.settings") as mock_settings:
            mock_settings.META_WHATSAPP_APP_SECRET = ""
            mock_settings.META_WHATSAPP_API_VERSION = "v21.0"
            mock_settings.META_WHATSAPP_PHONE_NUMBER_ID = "123"
            mock_settings.META_WHATSAPP_ACCESS_TOKEN = "token"
            provider = MetaCloudProvider()

        assert await provider.verify_webhook_signature(b"data", "any") is True

    async def test_build_text_payload(self):
        from modules.channel.whatsapp.meta_cloud import MetaCloudProvider
        from modules.channel.whatsapp.provider import WhatsAppMessage

        provider = MetaCloudProvider()
        msg = WhatsAppMessage(message_id=uuid.uuid4(), to_phone="+919876543210", text="Hello!")
        payload = provider._build_message_payload(msg)
        assert payload["type"] == "text"
        assert payload["text"]["body"] == "Hello!"
        assert payload["to"] == "919876543210"  # + stripped

    async def test_build_interactive_payload(self):
        from modules.channel.whatsapp.meta_cloud import MetaCloudProvider
        from modules.channel.whatsapp.provider import WhatsAppMessage

        provider = MetaCloudProvider()
        msg = WhatsAppMessage(
            message_id=uuid.uuid4(),
            to_phone="+919876543210",
            text="Choose one",
            buttons=[
                {"id": "btn_1", "title": "Option 1"},
                {"id": "btn_2", "title": "Option 2"},
            ],
        )
        payload = provider._build_message_payload(msg)
        assert payload["type"] == "interactive"
        assert len(payload["interactive"]["action"]["buttons"]) == 2

    async def test_build_media_payload(self):
        from modules.channel.whatsapp.meta_cloud import MetaCloudProvider
        from modules.channel.whatsapp.provider import WhatsAppMessage

        provider = MetaCloudProvider()
        msg = WhatsAppMessage(
            message_id=uuid.uuid4(),
            to_phone="+919876543210",
            media_url="https://example.com/video.mp4",
            media_type="video",
            text="Watch this",
        )
        payload = provider._build_message_payload(msg)
        assert payload["type"] == "video"
        assert payload["video"]["link"] == "https://example.com/video.mp4"
        assert payload["video"]["caption"] == "Watch this"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Bot Intent Classification Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestBotIntentClassification:
    def test_stop_intent_english(self):
        from modules.channel.whatsapp.bot import Intent, classify_intent
        from modules.channel.whatsapp.provider import WhatsAppIncomingMessage

        msg = WhatsAppIncomingMessage(from_phone="+91", message_type="text", text="STOP")
        assert classify_intent(msg) == Intent.STOP

    def test_stop_intent_hindi(self):
        from modules.channel.whatsapp.bot import Intent, classify_intent
        from modules.channel.whatsapp.provider import WhatsAppIncomingMessage

        msg = WhatsAppIncomingMessage(from_phone="+91", message_type="text", text="nahi chahiye band karo")
        assert classify_intent(msg) == Intent.STOP

    def test_training_intent(self):
        from modules.channel.whatsapp.bot import Intent, classify_intent
        from modules.channel.whatsapp.provider import WhatsAppIncomingMessage

        msg = WhatsAppIncomingMessage(from_phone="+91", message_type="text", text="mujhe training chahiye")
        assert classify_intent(msg) == Intent.TRAINING_REQUEST

    def test_adm_request_intent(self):
        from modules.channel.whatsapp.bot import Intent, classify_intent
        from modules.channel.whatsapp.provider import WhatsAppIncomingMessage

        msg = WhatsAppIncomingMessage(from_phone="+91", message_type="text", text="ADM se baat karni hai")
        assert classify_intent(msg) == Intent.ADM_REQUEST

    def test_product_question_intent(self):
        from modules.channel.whatsapp.bot import Intent, classify_intent
        from modules.channel.whatsapp.provider import WhatsAppIncomingMessage

        msg = WhatsAppIncomingMessage(from_phone="+91", message_type="text", text="term plan kya hai?")
        assert classify_intent(msg) == Intent.PRODUCT_QUESTION

    def test_commission_intent(self):
        from modules.channel.whatsapp.bot import Intent, classify_intent
        from modules.channel.whatsapp.provider import WhatsAppIncomingMessage

        msg = WhatsAppIncomingMessage(from_phone="+91", message_type="text", text="mera commission kab aayega?")
        assert classify_intent(msg) == Intent.COMMISSION_QUESTION

    def test_complaint_intent(self):
        from modules.channel.whatsapp.bot import Intent, classify_intent
        from modules.channel.whatsapp.provider import WhatsAppIncomingMessage

        msg = WhatsAppIncomingMessage(from_phone="+91", message_type="text", text="bahut problem hai dikkat ho rahi hai")
        assert classify_intent(msg) == Intent.COMPLAINT

    def test_greeting_intent(self):
        from modules.channel.whatsapp.bot import Intent, classify_intent
        from modules.channel.whatsapp.provider import WhatsAppIncomingMessage

        msg = WhatsAppIncomingMessage(from_phone="+91", message_type="text", text="Namaste")
        assert classify_intent(msg) == Intent.GREETING

    def test_button_click_intent(self):
        from modules.channel.whatsapp.bot import Intent, classify_intent
        from modules.channel.whatsapp.provider import WhatsAppIncomingMessage

        msg = WhatsAppIncomingMessage(
            from_phone="+91", message_type="interactive", button_payload="training_chahiye"
        )
        assert classify_intent(msg) == Intent.BUTTON_CLICK

    def test_media_received_intent(self):
        from modules.channel.whatsapp.bot import Intent, classify_intent
        from modules.channel.whatsapp.provider import WhatsAppIncomingMessage

        msg = WhatsAppIncomingMessage(from_phone="+91", message_type="image")
        assert classify_intent(msg) == Intent.MEDIA_RECEIVED

    def test_unknown_intent(self):
        from modules.channel.whatsapp.bot import Intent, classify_intent
        from modules.channel.whatsapp.provider import WhatsAppIncomingMessage

        msg = WhatsAppIncomingMessage(from_phone="+91", message_type="text", text="xyz random text")
        assert classify_intent(msg) == Intent.UNKNOWN

    def test_empty_text_unknown(self):
        from modules.channel.whatsapp.bot import Intent, classify_intent
        from modules.channel.whatsapp.provider import WhatsAppIncomingMessage

        msg = WhatsAppIncomingMessage(from_phone="+91", message_type="text", text="")
        assert classify_intent(msg) == Intent.UNKNOWN

    def test_stop_takes_priority_over_other_intents(self):
        from modules.channel.whatsapp.bot import Intent, classify_intent
        from modules.channel.whatsapp.provider import WhatsAppIncomingMessage

        # "stop" + "training" — STOP should take priority
        msg = WhatsAppIncomingMessage(from_phone="+91", message_type="text", text="stop training band karo")
        assert classify_intent(msg) == Intent.STOP


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Bot Message Handler Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestBotMessageHandler:
    def test_stop_response(self):
        from modules.channel.whatsapp.bot import handle_message
        from modules.channel.whatsapp.provider import WhatsAppIncomingMessage

        msg = WhatsAppIncomingMessage(from_phone="+91", message_type="text", text="STOP")
        response = handle_message(msg, agent_name="Rahul")
        assert response.emit_consent_revoked is True
        assert "Rahul" in response.text

    def test_greeting_response(self):
        from modules.channel.whatsapp.bot import handle_message
        from modules.channel.whatsapp.provider import WhatsAppIncomingMessage

        msg = WhatsAppIncomingMessage(from_phone="+91", message_type="text", text="Hello")
        response = handle_message(msg, agent_name="Rahul")
        assert "Rahul" in response.text
        assert response.buttons is not None

    def test_complaint_escalates_to_adm(self):
        from modules.channel.whatsapp.bot import handle_message
        from modules.channel.whatsapp.provider import WhatsAppIncomingMessage

        msg = WhatsAppIncomingMessage(from_phone="+91", message_type="text", text="problem hai dikkat")
        response = handle_message(msg, agent_name="Rahul", adm_name="Sharma")
        assert response.escalate_to_adm is True
        assert "Sharma" in response.text

    def test_image_media_escalates(self):
        from modules.channel.whatsapp.bot import handle_message
        from modules.channel.whatsapp.provider import WhatsAppIncomingMessage

        msg = WhatsAppIncomingMessage(from_phone="+91", message_type="image")
        response = handle_message(msg, agent_name="Rahul", adm_name="Sharma")
        assert response.escalate_to_adm is True

    def test_audio_media_acknowledged(self):
        from modules.channel.whatsapp.bot import handle_message
        from modules.channel.whatsapp.provider import WhatsAppIncomingMessage

        msg = WhatsAppIncomingMessage(from_phone="+91", message_type="audio")
        response = handle_message(msg, agent_name="Rahul")
        assert "voice note" in response.text


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Template Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestTemplates:
    def test_all_templates_registered(self):
        from modules.channel.whatsapp.templates import TEMPLATES

        expected = [
            "welcome_new_agent", "training_nudge", "training_quiz",
            "training_result_high", "training_result_medium", "training_result_low",
            "gentle_checkin", "sale_congratulation", "license_expiry_reminder",
            "adm_personalized",
        ]
        for name in expected:
            assert name in TEMPLATES, f"Template '{name}' not registered"

    def test_render_template_hindi(self):
        from modules.channel.whatsapp.templates import render_template

        result = render_template(
            "welcome_new_agent", "hi",
            {"agent_name": "Rahul", "company_name": "AARS Life", "adm_name": "Sharma"},
        )
        assert result is not None
        assert "Rahul" in result
        assert "AARS Life" in result
        assert "Sharma" in result

    def test_render_template_english(self):
        from modules.channel.whatsapp.templates import render_template

        result = render_template(
            "welcome_new_agent", "en",
            {"agent_name": "Rahul", "company_name": "AARS Life", "adm_name": "Sharma"},
        )
        assert result is not None
        assert "Welcome" in result
        assert "Rahul" in result

    def test_render_template_fallback_to_hindi(self):
        from modules.channel.whatsapp.templates import render_template

        result = render_template(
            "welcome_new_agent", "ta",  # Tamil — not defined
            {"agent_name": "Rahul", "company_name": "AARS Life", "adm_name": "Sharma"},
        )
        assert result is not None  # Falls back to Hindi

    def test_render_template_unknown_template(self):
        from modules.channel.whatsapp.templates import render_template

        assert render_template("nonexistent_template") is None

    def test_training_result_template_selection(self):
        from modules.channel.whatsapp.templates import get_training_result_template

        assert get_training_result_template(90) == "training_result_high"
        assert get_training_result_template(80) == "training_result_high"
        assert get_training_result_template(60) == "training_result_medium"
        assert get_training_result_template(50) == "training_result_medium"
        assert get_training_result_template(40) == "training_result_low"
        assert get_training_result_template(0) == "training_result_low"

    def test_get_template_buttons(self):
        from modules.channel.whatsapp.templates import get_template_buttons

        buttons = get_template_buttons("gentle_checkin")
        assert len(buttons) == 3
        assert "Training chahiye" in buttons

    def test_render_template_training_nudge(self):
        from modules.channel.whatsapp.templates import render_template

        result = render_template(
            "training_nudge", "hi",
            {"agent_name": "Rahul", "module_name": "Term Life Basics", "duration": "5", "module_description": "Learn about term life"},
        )
        assert "Term Life Basics" in result
        assert "5" in result


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Training Quiz Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrainingQuiz:
    def setup_method(self):
        from modules.channel.whatsapp.training import clear_all_quizzes
        clear_all_quizzes()

    def _make_module(self):
        from modules.channel.whatsapp.training import QuizQuestion, TrainingModule
        return TrainingModule(
            module_id="term_life_101",
            module_name="Term Life Basics",
            description="Learn about term life insurance",
            duration_minutes=5,
            questions=[
                QuizQuestion("Term life mein kya milta hai?", ["Death benefit", "Savings", "Loan"], 0),
                QuizQuestion("Term life ki premium kaisi hoti hai?", ["Low", "High", "No premium"], 0),
                QuizQuestion("Term life ka tenure?", ["Fixed", "Lifelong", "1 year"], 0),
            ],
        )

    def test_start_quiz(self):
        from modules.channel.whatsapp.training import start_quiz

        tid, aid = uuid.uuid4(), uuid.uuid4()
        module = self._make_module()
        result = start_quiz(tid, aid, module)
        assert "Sawaal 1/3" in result.text
        assert result.buttons is not None
        assert len(result.buttons) == 3

    def test_process_correct_answer(self):
        from modules.channel.whatsapp.training import process_quiz_answer, start_quiz

        tid, aid = uuid.uuid4(), uuid.uuid4()
        module = self._make_module()
        start_quiz(tid, aid, module)
        result = process_quiz_answer(tid, aid, 0)  # Correct
        assert "Sahi jawaab" in result.text
        assert not result.is_complete

    def test_process_wrong_answer(self):
        from modules.channel.whatsapp.training import process_quiz_answer, start_quiz

        tid, aid = uuid.uuid4(), uuid.uuid4()
        module = self._make_module()
        start_quiz(tid, aid, module)
        result = process_quiz_answer(tid, aid, 1)  # Wrong
        assert "Sahi jawaab tha" in result.text

    def test_full_quiz_flow_perfect_score(self):
        from modules.channel.whatsapp.training import process_quiz_answer, start_quiz

        tid, aid = uuid.uuid4(), uuid.uuid4()
        module = self._make_module()
        start_quiz(tid, aid, module)

        # Answer all 3 correctly
        process_quiz_answer(tid, aid, 0)
        process_quiz_answer(tid, aid, 0)
        result = process_quiz_answer(tid, aid, 0)

        assert result.is_complete is True
        assert result.score_percent == 100.0
        assert result.correct_count == 3
        assert "Shaandaar" in result.text

    def test_full_quiz_flow_partial_score(self):
        from modules.channel.whatsapp.training import process_quiz_answer, start_quiz

        tid, aid = uuid.uuid4(), uuid.uuid4()
        module = self._make_module()
        start_quiz(tid, aid, module)

        # 2 correct, 1 wrong
        process_quiz_answer(tid, aid, 0)  # Correct
        process_quiz_answer(tid, aid, 1)  # Wrong
        result = process_quiz_answer(tid, aid, 0)  # Correct

        assert result.is_complete is True
        assert result.score_percent == pytest.approx(66.7, abs=0.1)

    def test_full_quiz_flow_low_score(self):
        from modules.channel.whatsapp.training import process_quiz_answer, start_quiz

        tid, aid = uuid.uuid4(), uuid.uuid4()
        module = self._make_module()
        start_quiz(tid, aid, module)

        # All wrong
        process_quiz_answer(tid, aid, 1)
        process_quiz_answer(tid, aid, 1)
        result = process_quiz_answer(tid, aid, 1)

        assert result.is_complete is True
        assert result.score_percent == 0.0
        assert "Koi baat nahi" in result.text

    def test_has_active_quiz(self):
        from modules.channel.whatsapp.training import has_active_quiz, start_quiz

        tid, aid = uuid.uuid4(), uuid.uuid4()
        assert has_active_quiz(tid, aid) is False
        start_quiz(tid, aid, self._make_module())
        assert has_active_quiz(tid, aid) is True

    def test_cancel_quiz(self):
        from modules.channel.whatsapp.training import cancel_quiz, has_active_quiz, start_quiz

        tid, aid = uuid.uuid4(), uuid.uuid4()
        start_quiz(tid, aid, self._make_module())
        cancel_quiz(tid, aid)
        assert has_active_quiz(tid, aid) is False

    def test_no_active_quiz_answer(self):
        from modules.channel.whatsapp.training import process_quiz_answer

        tid, aid = uuid.uuid4(), uuid.uuid4()
        result = process_quiz_answer(tid, aid, 0)
        assert "Koi active quiz nahi" in result.text

    def test_parse_quiz_button_payload(self):
        from modules.channel.whatsapp.training import parse_quiz_button_payload

        result = parse_quiz_button_payload("quiz_term_life_101_1_2")
        assert result is not None
        module_id, q_idx, a_idx = result
        assert module_id == "term_life_101"
        assert q_idx == 1
        assert a_idx == 2

    def test_parse_quiz_button_payload_invalid(self):
        from modules.channel.whatsapp.training import parse_quiz_button_payload

        assert parse_quiz_button_payload("btn_something") is None
        assert parse_quiz_button_payload("quiz_") is None
        assert parse_quiz_button_payload("quiz_x") is None

    def test_empty_module_quiz(self):
        from modules.channel.whatsapp.training import TrainingModule, start_quiz

        tid, aid = uuid.uuid4(), uuid.uuid4()
        module = TrainingModule(
            module_id="empty", module_name="Empty", description="", duration_minutes=1
        )
        result = start_quiz(tid, aid, module)
        assert result.is_complete is True


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Webhook Endpoint Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestWhatsAppWebhook:
    async def test_webhook_verify_success(self, client: AsyncClient, wa_tenant: dict):
        """Meta webhook verification with correct token."""
        resp = await client.get(
            f"/api/v1/webhooks/whatsapp/{wa_tenant['slug']}",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "test-verify-token",
                "hub.challenge": "challenge-string-123",
            },
        )
        assert resp.status_code == 200
        assert resp.text == "challenge-string-123"

    async def test_webhook_verify_wrong_token(self, client: AsyncClient, wa_tenant: dict):
        """Meta webhook verification with wrong token returns 403."""
        resp = await client.get(
            f"/api/v1/webhooks/whatsapp/{wa_tenant['slug']}",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "challenge",
            },
        )
        assert resp.status_code == 403

    async def test_webhook_text_message(
        self, client: AsyncClient, wa_tenant: dict, wa_agent: dict,
    ):
        """Incoming text message webhook succeeds."""
        payload = _make_meta_webhook_payload(
            from_phone=wa_agent["phone"].lstrip("+"),
            message_type="text",
            text_body="Namaste",
        )
        resp = await client.post(
            f"/api/v1/webhooks/whatsapp/{wa_tenant['slug']}",
            json=payload,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["processed"] >= 1

    async def test_webhook_emits_agent_replied_signal(
        self, client: AsyncClient, wa_tenant: dict, wa_agent: dict,
    ):
        """Webhook for text message emits WHATSAPP_AGENT_REPLIED signal."""
        payload = _make_meta_webhook_payload(
            from_phone=wa_agent["phone"].lstrip("+"),
            message_type="text",
            text_body="Hello training chahiye",
        )
        resp = await client.post(
            f"/api/v1/webhooks/whatsapp/{wa_tenant['slug']}",
            json=payload,
        )
        assert resp.status_code == 200

        with sync_engine.begin() as conn:
            signals = conn.execute(
                text(
                    "SELECT signal_type, payload FROM signals "
                    "WHERE tenant_id = :tid AND agent_id = :aid "
                    "ORDER BY created_at DESC"
                ),
                {"tid": str(wa_tenant["id"]), "aid": str(wa_agent["id"])},
            ).fetchall()

        signal_types = [s[0] for s in signals]
        assert SignalType.WHATSAPP_AGENT_REPLIED in signal_types

    async def test_webhook_delivery_status(
        self, client: AsyncClient, wa_tenant: dict,
    ):
        """Delivery status webhook emits WHATSAPP_MESSAGE_DELIVERED signal."""
        payload = _make_status_webhook_payload(status="delivered")
        resp = await client.post(
            f"/api/v1/webhooks/whatsapp/{wa_tenant['slug']}",
            json=payload,
        )
        assert resp.status_code == 200

        with sync_engine.begin() as conn:
            signals = conn.execute(
                text(
                    "SELECT signal_type FROM signals "
                    "WHERE tenant_id = :tid AND signal_type = :st"
                ),
                {"tid": str(wa_tenant["id"]), "st": SignalType.WHATSAPP_MESSAGE_DELIVERED},
            ).fetchall()
        assert len(signals) >= 1

    async def test_webhook_read_status(
        self, client: AsyncClient, wa_tenant: dict,
    ):
        """Read status webhook emits WHATSAPP_MESSAGE_READ signal."""
        payload = _make_status_webhook_payload(status="read")
        resp = await client.post(
            f"/api/v1/webhooks/whatsapp/{wa_tenant['slug']}",
            json=payload,
        )
        assert resp.status_code == 200

        with sync_engine.begin() as conn:
            signals = conn.execute(
                text(
                    "SELECT signal_type FROM signals "
                    "WHERE tenant_id = :tid AND signal_type = :st"
                ),
                {"tid": str(wa_tenant["id"]), "st": SignalType.WHATSAPP_MESSAGE_READ},
            ).fetchall()
        assert len(signals) >= 1

    async def test_webhook_unknown_tenant(self, client: AsyncClient):
        """Webhook for unknown tenant returns 404."""
        payload = _make_meta_webhook_payload()
        resp = await client.post(
            "/api/v1/webhooks/whatsapp/nonexistent-tenant-xyz",
            json=payload,
        )
        assert resp.status_code == 404

    async def test_webhook_stop_emits_consent_signal(
        self, client: AsyncClient, wa_tenant: dict, wa_agent: dict,
    ):
        """STOP message emits CONSENT_CHANGED signal."""
        payload = _make_meta_webhook_payload(
            from_phone=wa_agent["phone"].lstrip("+"),
            message_type="text",
            text_body="STOP band karo",
        )
        resp = await client.post(
            f"/api/v1/webhooks/whatsapp/{wa_tenant['slug']}",
            json=payload,
        )
        assert resp.status_code == 200

        with sync_engine.begin() as conn:
            signals = conn.execute(
                text(
                    "SELECT signal_type, payload FROM signals "
                    "WHERE tenant_id = :tid AND signal_type = :st"
                ),
                {"tid": str(wa_tenant["id"]), "st": SignalType.CONSENT_CHANGED},
            ).fetchall()
        assert len(signals) >= 1
        consent_payload = signals[0][1]
        assert consent_payload["consent_type"] == "whatsapp"
        assert consent_payload["new_status"] == ConsentStatus.REVOKED

    async def test_webhook_complaint_emits_adm_nudge(
        self, client: AsyncClient, wa_tenant: dict, wa_agent: dict,
    ):
        """Complaint triggers ADM_NUDGE_RECEIVED signal."""
        payload = _make_meta_webhook_payload(
            from_phone=wa_agent["phone"].lstrip("+"),
            message_type="text",
            text_body="bahut problem hai dikkat ho rahi hai",
        )
        resp = await client.post(
            f"/api/v1/webhooks/whatsapp/{wa_tenant['slug']}",
            json=payload,
        )
        assert resp.status_code == 200

        with sync_engine.begin() as conn:
            signals = conn.execute(
                text(
                    "SELECT signal_type, payload FROM signals "
                    "WHERE tenant_id = :tid AND signal_type = :st"
                ),
                {"tid": str(wa_tenant["id"]), "st": SignalType.ADM_NUDGE_RECEIVED},
            ).fetchall()
        assert len(signals) >= 1

    async def test_webhook_unknown_phone(
        self, client: AsyncClient, wa_tenant: dict,
    ):
        """Webhook with unknown phone still succeeds (agent_id null in signal)."""
        payload = _make_meta_webhook_payload(
            from_phone="910000000000",
            message_type="text",
            text_body="Hello",
        )
        resp = await client.post(
            f"/api/v1/webhooks/whatsapp/{wa_tenant['slug']}",
            json=payload,
        )
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Sending Service Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSendingService:
    async def test_send_template_consent_denied(self):
        from modules.channel.whatsapp.service import send_template_to_agent
        from config.database import async_session_factory

        async with async_session_factory() as db:
            result = await send_template_to_agent(
                db=db,
                tenant_id=uuid.uuid4(),
                agent_id=uuid.uuid4(),
                agent_phone="+919876543210",
                consent_whatsapp=ConsentStatus.DENIED,
                template_name="welcome_new_agent",
            )
        assert result.success is False
        assert result.error == "consent_denied"

    async def test_send_template_consent_revoked(self):
        from modules.channel.whatsapp.service import send_template_to_agent
        from config.database import async_session_factory

        async with async_session_factory() as db:
            result = await send_template_to_agent(
                db=db,
                tenant_id=uuid.uuid4(),
                agent_id=uuid.uuid4(),
                agent_phone="+919876543210",
                consent_whatsapp=ConsentStatus.REVOKED,
                template_name="welcome_new_agent",
            )
        assert result.success is False
        assert result.error == "consent_denied"

    async def test_send_text_consent_denied(self):
        from modules.channel.whatsapp.service import send_text_to_agent
        from config.database import async_session_factory

        async with async_session_factory() as db:
            result = await send_text_to_agent(
                db=db,
                tenant_id=uuid.uuid4(),
                agent_id=uuid.uuid4(),
                agent_phone="+919876543210",
                consent_whatsapp=ConsentStatus.DENIED,
                text="Hello",
            )
        assert result.success is False
        assert result.error == "consent_denied"

    async def test_send_template_success(self, wa_tenant: dict, wa_agent: dict):
        from modules.channel.whatsapp.service import send_template_to_agent
        from config.database import async_session_factory

        async with async_session_factory() as db:
            result = await send_template_to_agent(
                db=db,
                tenant_id=wa_tenant["id"],
                agent_id=wa_agent["id"],
                agent_phone=wa_agent["phone"],
                consent_whatsapp=ConsentStatus.GRANTED,
                template_name="welcome_new_agent",
                template_params={"agent_name": "Rahul", "company_name": "AARS", "adm_name": "Sharma"},
            )
            await db.commit()
        assert result.success is True
        assert result.message_id is not None

    async def test_send_text_success(self, wa_tenant: dict, wa_agent: dict):
        from modules.channel.whatsapp.service import send_text_to_agent
        from config.database import async_session_factory

        async with async_session_factory() as db:
            result = await send_text_to_agent(
                db=db,
                tenant_id=wa_tenant["id"],
                agent_id=wa_agent["id"],
                agent_phone=wa_agent["phone"],
                consent_whatsapp=ConsentStatus.GRANTED,
                text="Hello Rahul!",
            )
            await db.commit()
        assert result.success is True

    async def test_send_template_emits_signal(self, wa_tenant: dict, wa_agent: dict):
        from modules.channel.whatsapp.service import send_template_to_agent
        from config.database import async_session_factory

        async with async_session_factory() as db:
            await send_template_to_agent(
                db=db,
                tenant_id=wa_tenant["id"],
                agent_id=wa_agent["id"],
                agent_phone=wa_agent["phone"],
                consent_whatsapp=ConsentStatus.GRANTED,
                template_name="training_nudge",
                template_params={"agent_name": "Rahul", "module_name": "M1", "duration": "5", "module_description": "desc"},
            )
            await db.commit()

        with sync_engine.begin() as conn:
            signals = conn.execute(
                text(
                    "SELECT signal_type, payload FROM signals "
                    "WHERE tenant_id = :tid AND signal_type = :st"
                ),
                {"tid": str(wa_tenant["id"]), "st": SignalType.WHATSAPP_MESSAGE_SENT},
            ).fetchall()
        assert len(signals) >= 1
        assert signals[0][1]["purpose"] == "TRAINING"

    async def test_purpose_inference(self):
        from modules.channel.whatsapp.service import _infer_purpose

        assert _infer_purpose("training_nudge") == "TRAINING"
        assert _infer_purpose("gentle_checkin") == "NUDGE"
        assert _infer_purpose("license_expiry_reminder") == "REMINDER"
        assert _infer_purpose("sale_congratulation") == "CONGRATULATION"
        assert _infer_purpose("welcome_new_agent") == "INFO"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Rate Limiting Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestWhatsAppRateLimiting:
    @pytest.fixture
    async def redis(self):
        from redis.asyncio import Redis
        from config.settings import settings
        client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        yield client
        # Clean up
        tid = "00000000-0000-0000-0000-000000000088"
        keys = await client.keys(f"whatsapp:*:{tid}*")
        if keys:
            await client.delete(*keys)
        await client.aclose()

    @pytest.fixture
    async def limiter(self, redis):
        from modules.channel.rate_limiter import ChannelRateLimiter
        return ChannelRateLimiter(redis)

    async def test_send_template_rate_limited(self, limiter, redis):
        from modules.channel.whatsapp.service import send_template_to_agent
        from config.database import async_session_factory

        tid = uuid.UUID("00000000-0000-0000-0000-000000000088")
        aid = uuid.uuid4()

        # Exhaust daily limit
        for _ in range(3):
            await limiter.record_whatsapp_message(tid, aid)

        async with async_session_factory() as db:
            result = await send_template_to_agent(
                db=db,
                tenant_id=tid,
                agent_id=aid,
                agent_phone="+919876543210",
                consent_whatsapp=ConsentStatus.GRANTED,
                template_name="training_nudge",
                rate_limiter=limiter,
            )
        assert result.success is False
        assert result.error == "rate_limited"

        # Clean up
        await redis.delete(f"whatsapp:daily:{tid}:{aid}")


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Tenant Isolation Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestWhatsAppTenantIsolation:
    async def test_webhook_signals_isolated(self, client: AsyncClient):
        """Signals from tenant A's WhatsApp webhook don't appear in tenant B."""
        t1_id, t2_id = uuid.uuid4(), uuid.uuid4()
        t1_slug = f"waiso-a-{t1_id.hex[:6]}"
        t2_slug = f"waiso-b-{t2_id.hex[:6]}"

        with sync_engine.begin() as conn:
            for tid, slug in [(t1_id, t1_slug), (t2_id, t2_slug)]:
                conn.execute(
                    text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
                    {"id": str(tid), "name": f"Tenant {slug}", "slug": slug},
                )

        try:
            # Send webhook to tenant A
            payload = _make_meta_webhook_payload(message_type="text", text_body="Hello from A")
            resp = await client.post(
                f"/api/v1/webhooks/whatsapp/{t1_slug}",
                json=payload,
            )
            assert resp.status_code == 200

            # Verify tenant B has no signals
            with sync_engine.begin() as conn:
                count = conn.execute(
                    text("SELECT COUNT(*) FROM signals WHERE tenant_id = :tid"),
                    {"tid": str(t2_id)},
                ).scalar()
            assert count == 0

            # Verify tenant A has signals
            with sync_engine.begin() as conn:
                count_a = conn.execute(
                    text("SELECT COUNT(*) FROM signals WHERE tenant_id = :tid"),
                    {"tid": str(t1_id)},
                ).scalar()
            assert count_a >= 1

        finally:
            with sync_engine.begin() as conn:
                conn.execute(text("DELETE FROM signals WHERE tenant_id IN (:t1, :t2)"),
                             {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM tenants WHERE id IN (:t1, :t2)"),
                             {"t1": str(t1_id), "t2": str(t2_id)})


# ═══════════════════════════════════════════════════════════════════════════════
# 10. App Route Registration Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestAppRouteRegistration:
    def test_whatsapp_webhook_routes_registered(self, app):
        """WhatsApp webhook routes are registered in the app."""
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/api/v1/webhooks/whatsapp/{tenant_slug}" in routes

    def test_voice_webhook_routes_still_registered(self, app):
        """Voice webhook routes remain registered (regression)."""
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/api/v1/webhooks/voice/{tenant_slug}" in routes
