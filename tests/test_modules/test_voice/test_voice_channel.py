"""Tests for Voice AI Channel (Slice 4).

Covers: provider interface, mock provider, Vibrium adapter, NLU extraction,
conversation flows, DND checker, rate limiter, webhook endpoint, TRAI hours,
signal emission, and tenant isolation.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, time, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from api.app import create_app
from config.database import sync_engine
from core.enums import ContactOutcome, DormancyReasonCode, SentimentLabel


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
def voice_tenant() -> dict:
    """Create a test tenant with a known slug for webhook tests."""
    tenant_id = uuid.uuid4()
    slug = f"voice-{tenant_id.hex[:8]}"
    with sync_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO tenants (id, name, slug, subscription_tier, is_active, config) "
                "VALUES (:id, :name, :slug, 'trial', true, '{}'::jsonb)"
            ),
            {"id": str(tenant_id), "name": f"Voice Test {slug}", "slug": slug},
        )
    yield {"id": tenant_id, "slug": slug}
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM signals WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM agents WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM users WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM tenants WHERE id = :tid"), {"tid": str(tenant_id)})


@pytest.fixture
def voice_agent(voice_tenant: dict) -> dict:
    """Create a test agent with a known phone number."""
    agent_id = uuid.uuid4()
    phone = "+919876543210"
    with sync_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO agents (id, tenant_id, agent_code, full_name, phone, lifecycle_state) "
                "VALUES (:id, :tid, :code, :name, :phone, 'dormant')"
            ),
            {
                "id": str(agent_id),
                "tid": str(voice_tenant["id"]),
                "code": f"VA-{agent_id.hex[:8]}",
                "name": "Voice Test Agent",
                "phone": phone,
            },
        )
    yield {"id": agent_id, "phone": phone, "tenant_id": voice_tenant["id"]}
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM signals WHERE agent_id = :aid"), {"aid": str(agent_id)})
        conn.execute(text("DELETE FROM agents WHERE id = :aid"), {"aid": str(agent_id)})


def _make_webhook_payload(
    call_id: str | None = None,
    phone: str = "+919876543210",
    outcome: str = "answered",
    duration: int = 120,
    transcript: str = "Test transcript",
    sentiment: str = "positive",
    recording_url: str | None = None,
) -> dict:
    return {
        "call_id": call_id or str(uuid.uuid4()),
        "phone_number": phone,
        "outcome": outcome,
        "duration_seconds": duration,
        "language": "hi",
        "transcript": transcript,
        "summary": "Test summary",
        "sentiment": sentiment,
        "analysis": {"raw": "test"},
        "recording_url": recording_url,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Provider Interface Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestMockProvider:
    async def test_initiate_call(self):
        from modules.channel.voice.mock import MockVoiceProvider
        from modules.channel.voice.provider import VoiceCallRequest

        provider = MockVoiceProvider()
        request = VoiceCallRequest(
            call_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            agent_id=uuid.uuid4(),
            agent_phone="+919876543210",
            caller_id="+911234567890",
            language="hi",
            conversation_guide="test",
        )
        call_id = await provider.initiate_call(request)
        assert call_id.startswith("mock-")
        assert len(provider.calls) == 1

    async def test_handle_callback_default(self):
        from modules.channel.voice.mock import MockVoiceProvider

        provider = MockVoiceProvider()
        result = await provider.handle_callback({"test": True})
        assert result.outcome == ContactOutcome.COMPLETED
        assert result.duration_seconds == 120

    async def test_set_next_result(self):
        from modules.channel.voice.mock import MockVoiceProvider
        from modules.channel.voice.provider import VoiceCallResult

        provider = MockVoiceProvider()
        custom = VoiceCallResult(
            call_id=uuid.uuid4(),
            outcome=ContactOutcome.BUSY,
            duration_seconds=5,
            language_detected="en",
        )
        provider.set_next_result(custom)
        result = await provider.handle_callback({})
        assert result.outcome == ContactOutcome.BUSY

    async def test_verify_signature_always_true(self):
        from modules.channel.voice.mock import MockVoiceProvider

        provider = MockVoiceProvider()
        assert await provider.verify_webhook_signature(b"anything", "any") is True

    async def test_reset(self):
        from modules.channel.voice.mock import MockVoiceProvider
        from modules.channel.voice.provider import VoiceCallRequest

        provider = MockVoiceProvider()
        req = VoiceCallRequest(
            call_id=uuid.uuid4(), tenant_id=uuid.uuid4(), agent_id=uuid.uuid4(),
            agent_phone="+919876543210", caller_id="+911234567890",
            language="hi", conversation_guide="test",
        )
        await provider.initiate_call(req)
        assert len(provider.calls) == 1
        provider.reset()
        assert len(provider.calls) == 0


class TestVibriumProvider:
    async def test_handle_callback_answered(self):
        from modules.channel.voice.vibrium import VibriumProvider

        provider = VibriumProvider(api_url="", api_key="", webhook_secret="")
        payload = _make_webhook_payload(outcome="answered", sentiment="positive")
        result = await provider.handle_callback(payload)
        assert result.outcome == ContactOutcome.ANSWERED
        assert result.sentiment == SentimentLabel.POSITIVE
        assert result.duration_seconds == 120
        assert result.transcript_text == "Test transcript"

    async def test_handle_callback_not_answered(self):
        from modules.channel.voice.vibrium import VibriumProvider

        provider = VibriumProvider(api_url="", api_key="", webhook_secret="")
        result = await provider.handle_callback(_make_webhook_payload(outcome="no_answer"))
        assert result.outcome == ContactOutcome.NOT_ANSWERED

    async def test_handle_callback_unknown_outcome(self):
        from modules.channel.voice.vibrium import VibriumProvider

        provider = VibriumProvider(api_url="", api_key="", webhook_secret="")
        result = await provider.handle_callback(_make_webhook_payload(outcome="xyz_unknown"))
        assert result.outcome == ContactOutcome.FAILED_TECHNICAL

    async def test_verify_signature_valid(self):
        from modules.channel.voice.vibrium import VibriumProvider

        secret = "test-secret-123"
        provider = VibriumProvider(api_url="", api_key="", webhook_secret=secret)
        payload = b'{"call_id": "test"}'
        sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert await provider.verify_webhook_signature(payload, sig) is True

    async def test_verify_signature_invalid(self):
        from modules.channel.voice.vibrium import VibriumProvider

        provider = VibriumProvider(api_url="", api_key="", webhook_secret="secret")
        assert await provider.verify_webhook_signature(b"data", "wrong-sig") is False

    async def test_verify_signature_no_secret_configured(self):
        from modules.channel.voice.vibrium import VibriumProvider

        provider = VibriumProvider(api_url="", api_key="", webhook_secret="")
        assert await provider.verify_webhook_signature(b"data", "any") is True

    async def test_outcome_mapping_all_values(self):
        from modules.channel.voice.vibrium import VibriumProvider

        provider = VibriumProvider(api_url="", api_key="", webhook_secret="")
        mapping = {
            "answered": ContactOutcome.ANSWERED,
            "completed": ContactOutcome.COMPLETED,
            "busy": ContactOutcome.BUSY,
            "switched_off": ContactOutcome.SWITCHED_OFF,
            "wrong_number": ContactOutcome.WRONG_NUMBER,
            "failed": ContactOutcome.FAILED_TECHNICAL,
        }
        for raw, expected in mapping.items():
            result = await provider.handle_callback(_make_webhook_payload(outcome=raw))
            assert result.outcome == expected, f"Outcome '{raw}' should map to {expected}"


# ═══════════════════════════════════════════════════════════════════════════════
# NLU Extraction Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestNLUExtraction:
    def test_empty_transcript(self):
        from modules.channel.voice.nlu import extract_from_transcript

        result = extract_from_transcript("", provider_sentiment=SentimentLabel.NEUTRAL)
        assert result.sentiment == SentimentLabel.NEUTRAL
        assert result.dormancy_reasons == []

    def test_product_knowledge_insufficient(self):
        from modules.channel.voice.nlu import extract_from_transcript

        text = "Mujhe samajh nahi aata ki term plan kya hai"
        result = extract_from_transcript(text)
        codes = [r["code"] for r in result.dormancy_reasons]
        assert DormancyReasonCode.PRODUCT_KNOWLEDGE_INSUFFICIENT.value in codes

    def test_sales_skills_lacking(self):
        from modules.channel.voice.nlu import extract_from_transcript

        text = "Log mante nahi hain, bech nahi pa raha hoon"
        result = extract_from_transcript(text)
        codes = [r["code"] for r in result.dormancy_reasons]
        assert DormancyReasonCode.SALES_SKILLS_LACKING.value in codes

    def test_adm_never_contacted(self):
        from modules.channel.voice.nlu import extract_from_transcript

        text = "Manager ne kabhi call nahi kiya mujhe"
        result = extract_from_transcript(text)
        codes = [r["code"] for r in result.dormancy_reasons]
        assert DormancyReasonCode.ADM_NEVER_CONTACTED.value in codes
        assert result.adm_mentioned is True

    def test_commission_concerns(self):
        from modules.channel.voice.nlu import extract_from_transcript

        text = "Commission bahut kam hai, paisa nahi milta"
        result = extract_from_transcript(text)
        assert result.commission_concerns is True
        codes = [r["code"] for r in result.dormancy_reasons]
        assert DormancyReasonCode.COMMISSION_TOO_LOW.value in codes

    def test_competitor_mentions(self):
        from modules.channel.voice.nlu import extract_from_transcript

        text = "LIC mein zyada milta hai, HDFC Life bhi better hai"
        result = extract_from_transcript(text)
        assert "lic" in result.competitor_mentions
        assert "hdfc life" in result.competitor_mentions

    def test_product_interests(self):
        from modules.channel.voice.nlu import extract_from_transcript

        text = "I want to know about term plan and health insurance"
        result = extract_from_transcript(text)
        assert "term_life" in result.product_interests
        assert "health" in result.product_interests

    def test_health_issues(self):
        from modules.channel.voice.nlu import extract_from_transcript

        text = "Tabiyat kharab thi, hospital mein tha"
        result = extract_from_transcript(text)
        codes = [r["code"] for r in result.dormancy_reasons]
        assert DormancyReasonCode.HEALTH_ISSUES.value in codes

    def test_relocated(self):
        from modules.channel.voice.nlu import extract_from_transcript

        text = "Main shift ho gaya doosre shehar mein"
        result = extract_from_transcript(text)
        codes = [r["code"] for r in result.dormancy_reasons]
        assert DormancyReasonCode.RELOCATED.value in codes

    def test_lost_interest(self):
        from modules.channel.voice.nlu import extract_from_transcript

        text = "Interest nahi hai ab, nahi karna hai"
        result = extract_from_transcript(text)
        codes = [r["code"] for r in result.dormancy_reasons]
        assert DormancyReasonCode.LOST_INTEREST.value in codes

    def test_other_employment(self):
        from modules.channel.voice.nlu import extract_from_transcript

        text = "Job lag gayi meri, full time kaam kar raha hoon"
        result = extract_from_transcript(text)
        codes = [r["code"] for r in result.dormancy_reasons]
        assert DormancyReasonCode.OTHER_EMPLOYMENT.value in codes

    def test_multiple_dormancy_reasons(self):
        from modules.channel.voice.nlu import extract_from_transcript

        text = "Commission bahut kam hai aur form bahut mushkil hai bharna"
        result = extract_from_transcript(text)
        codes = [r["code"] for r in result.dormancy_reasons]
        assert len(codes) >= 2
        assert DormancyReasonCode.COMMISSION_TOO_LOW.value in codes
        assert DormancyReasonCode.PROPOSAL_PROCESS_COMPLEX.value in codes

    def test_adm_negative_sentiment(self):
        from modules.channel.voice.nlu import extract_from_transcript

        text = "ADM ne kabhi help nahi kiya"
        result = extract_from_transcript(text)
        assert result.adm_mentioned is True
        assert result.adm_sentiment == SentimentLabel.NEGATIVE

    def test_adm_positive_sentiment(self):
        from modules.channel.voice.nlu import extract_from_transcript

        text = "ADM acche hain, unhone support kiya"
        result = extract_from_transcript(text)
        assert result.adm_mentioned is True
        assert result.adm_sentiment == SentimentLabel.POSITIVE

    def test_action_items_detected(self):
        from modules.channel.voice.nlu import extract_from_transcript

        text = "Mujhe training video bhej do aur ADM se baat karao"
        result = extract_from_transcript(text)
        assert len(result.action_items) >= 1

    def test_key_quotes_extracted(self):
        from modules.channel.voice.nlu import extract_from_transcript

        text = "Main bahut pareshan hoon. Commission nahi milta. Interest nahi hai ab."
        result = extract_from_transcript(text)
        assert len(result.key_quotes) >= 1

    def test_provider_sentiment_used_when_available(self):
        from modules.channel.voice.nlu import extract_from_transcript

        result = extract_from_transcript(
            "some random text",
            provider_sentiment=SentimentLabel.FRUSTRATED,
        )
        assert result.sentiment == SentimentLabel.FRUSTRATED

    def test_sentiment_inferred_negative(self):
        from modules.channel.voice.nlu import extract_from_transcript

        text = "Problem hai, mushkil hai, nahi hota, pareshan hoon"
        result = extract_from_transcript(text, provider_sentiment=None)
        assert result.sentiment == SentimentLabel.NEGATIVE

    def test_sentiment_inferred_positive(self):
        from modules.channel.voice.nlu import extract_from_transcript

        text = "Accha hai, haan interested hoon, ready hoon, chahiye mujhe"
        result = extract_from_transcript(text, provider_sentiment=None)
        assert result.sentiment == SentimentLabel.POSITIVE

    def test_technology_barriers(self):
        from modules.channel.voice.nlu import extract_from_transcript

        text = "App kaam nahi karta mera phone mein"
        result = extract_from_transcript(text)
        codes = [r["code"] for r in result.dormancy_reasons]
        assert DormancyReasonCode.TECHNOLOGY_BARRIERS.value in codes

    def test_confidence_scores_present(self):
        from modules.channel.voice.nlu import extract_from_transcript

        text = "Mujhe samajh nahi aata product ke baare mein"
        result = extract_from_transcript(text)
        for reason in result.dormancy_reasons:
            assert "confidence" in reason
            assert 0 < reason["confidence"] <= 1.0
            assert "matched_phrases" in reason


# ═══════════════════════════════════════════════════════════════════════════════
# Conversation Flow Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestConversationFlows:
    def test_all_flows_exist(self):
        from modules.channel.voice.conversation_flows import FLOWS

        assert "first_contact" in FLOWS
        assert "dormant_check_in" in FLOWS
        assert "congratulation" in FLOWS
        assert "license_renewal" in FLOWS

    def test_get_flow(self):
        from modules.channel.voice.conversation_flows import get_flow

        flow = get_flow("first_contact")
        assert flow is not None
        assert flow.flow_id == "first_contact"
        assert flow.max_duration_seconds == 300

    def test_get_flow_unknown(self):
        from modules.channel.voice.conversation_flows import get_flow

        assert get_flow("nonexistent") is None

    def test_render_opening(self):
        from modules.channel.voice.conversation_flows import FIRST_CONTACT, render_opening

        context = {
            "agent_name": "Rahul",
            "persona_name": "Priya",
            "company_name": "AARS Life",
            "adm_name": "Mr. Sharma",
        }
        opening = render_opening(FIRST_CONTACT, context)
        assert "Rahul" in opening
        assert "Priya" in opening
        assert "AARS Life" in opening

    def test_render_opening_missing_key(self):
        from modules.channel.voice.conversation_flows import FIRST_CONTACT, render_opening

        opening = render_opening(FIRST_CONTACT, {})
        assert "{agent_name}" in opening  # Falls back to template with placeholders

    def test_dormant_checkin_longer_duration(self):
        from modules.channel.voice.conversation_flows import DORMANT_CHECK_IN

        assert DORMANT_CHECK_IN.max_duration_seconds == 480

    def test_congratulation_shorter_duration(self):
        from modules.channel.voice.conversation_flows import CONGRATULATION

        assert CONGRATULATION.max_duration_seconds == 180


# ═══════════════════════════════════════════════════════════════════════════════
# DND Checker Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestDNDChecker:
    async def test_mock_default_not_registered(self):
        from modules.channel.voice.dnd_checker import MockDNDChecker

        checker = MockDNDChecker()
        result = await checker.check("+919876543210")
        assert result.is_registered is False
        assert result.can_call is True

    async def test_mock_registered_number(self):
        from modules.channel.voice.dnd_checker import MockDNDChecker

        checker = MockDNDChecker()
        checker.set_registered("+919876543210")
        result = await checker.check("+919876543210")
        assert result.is_registered is True
        assert result.can_call is True  # transactional calls still allowed

    async def test_mock_promotional_dnd_blocked(self):
        from modules.channel.voice.dnd_checker import DNDCheckResult, MockDNDChecker

        checker = MockDNDChecker()
        checker.set_registered("+919876543210")
        result = await checker.check("+919876543210")
        # Simulate promotional call type
        result.call_type = "promotional"
        assert result.can_call is False

    async def test_batch_check(self):
        from modules.channel.voice.dnd_checker import MockDNDChecker

        checker = MockDNDChecker()
        checker.set_registered("+919111111111")
        results = await checker.batch_check(["+919111111111", "+919222222222"])
        assert len(results) == 2
        assert results[0].is_registered is True
        assert results[1].is_registered is False

    async def test_staleness_check(self):
        from modules.channel.voice.dnd_checker import DNDCheckResult

        old = DNDCheckResult(
            phone="+919876543210",
            is_registered=False,
            checked_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        assert old.is_stale is True

        recent = DNDCheckResult(
            phone="+919876543210",
            is_registered=False,
            checked_at=datetime.now(timezone.utc),
        )
        assert recent.is_stale is False

    async def test_clear(self):
        from modules.channel.voice.dnd_checker import MockDNDChecker

        checker = MockDNDChecker()
        checker.set_registered("+919876543210")
        checker.clear()
        result = await checker.check("+919876543210")
        assert result.is_registered is False


# ═══════════════════════════════════════════════════════════════════════════════
# Rate Limiter Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestRateLimiter:
    @pytest.fixture
    async def redis(self):
        from redis.asyncio import Redis
        from config.settings import settings
        client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        yield client
        # Clean up rate limit keys after test
        tid = "00000000-0000-0000-0000-000000000099"
        keys = await client.keys(f"voice:*:{tid}*")
        keys += await client.keys(f"whatsapp:*:{tid}*")
        if keys:
            await client.delete(*keys)
        await client.aclose()

    @pytest.fixture
    async def limiter(self, redis):
        from modules.channel.rate_limiter import ChannelRateLimiter
        rl = ChannelRateLimiter(redis)
        yield rl

    async def test_voice_rate_under_limit(self, limiter):
        tid = uuid.UUID("00000000-0000-0000-0000-000000000099")
        result = await limiter.check_voice_rate(tid)
        assert result.allowed is True

    async def test_voice_concurrent_acquire_release(self, limiter, redis):
        tid = uuid.UUID("00000000-0000-0000-0000-000000000099")
        # Clean up before test
        await redis.delete(f"voice:concurrent:{tid}")

        assert await limiter.acquire_voice_slot(tid) is True
        assert await limiter.acquire_voice_slot(tid) is True
        await limiter.release_voice_slot(tid)
        await limiter.release_voice_slot(tid)
        await redis.delete(f"voice:concurrent:{tid}")

    async def test_voice_concurrent_limit_exceeded(self, limiter, redis):
        tid = uuid.UUID("00000000-0000-0000-0000-000000000099")
        await redis.delete(f"voice:concurrent:{tid}")

        # Fill up all 5 slots
        for _ in range(5):
            assert await limiter.acquire_voice_slot(tid) is True

        # 6th should fail
        assert await limiter.acquire_voice_slot(tid) is False

        # Clean up
        for _ in range(5):
            await limiter.release_voice_slot(tid)
        await redis.delete(f"voice:concurrent:{tid}")

    async def test_whatsapp_rate_under_limit(self, limiter):
        tid = uuid.UUID("00000000-0000-0000-0000-000000000099")
        agent_id = uuid.uuid4()
        result = await limiter.check_whatsapp_rate(tid, agent_id)
        assert result.allowed is True

    async def test_whatsapp_daily_per_agent_limit(self, limiter, redis):
        tid = uuid.UUID("00000000-0000-0000-0000-000000000099")
        agent_id = uuid.uuid4()
        key = f"whatsapp:daily:{tid}:{agent_id}"
        await redis.delete(key)

        # Send 3 messages (the daily limit)
        for _ in range(3):
            await limiter.record_whatsapp_message(tid, agent_id)

        result = await limiter._check_whatsapp_daily_per_agent(tid, agent_id)
        assert result.allowed is False
        assert result.current_count == 3

        await redis.delete(key)

    async def test_voice_record_and_hourly_check(self, limiter, redis):
        tid = uuid.UUID("00000000-0000-0000-0000-000000000099")
        key = f"voice:hourly:{tid}"
        await redis.delete(key)

        await limiter.record_voice_call(tid)
        result = await limiter._check_voice_hourly(tid)
        assert result.allowed is True
        assert result.current_count == 1

        await redis.delete(key)


# ═══════════════════════════════════════════════════════════════════════════════
# TRAI Hours Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestTRAIHours:
    def test_within_hours_morning(self):
        from modules.channel.voice.webhook_router import _TRAI_START, _TRAI_END

        t = time(10, 0)
        assert _TRAI_START <= t <= _TRAI_END

    def test_within_hours_boundary_start(self):
        from modules.channel.voice.webhook_router import _TRAI_START, _TRAI_END

        assert _TRAI_START <= time(9, 0) <= _TRAI_END

    def test_within_hours_boundary_end(self):
        from modules.channel.voice.webhook_router import _TRAI_START, _TRAI_END

        assert _TRAI_START <= time(21, 0) <= _TRAI_END

    def test_outside_hours_early(self):
        from modules.channel.voice.webhook_router import _TRAI_START, _TRAI_END

        t = time(6, 0)
        assert not (_TRAI_START <= t <= _TRAI_END)

    def test_outside_hours_late(self):
        from modules.channel.voice.webhook_router import _TRAI_START, _TRAI_END

        t = time(22, 0)
        assert not (_TRAI_START <= t <= _TRAI_END)

    def test_is_within_trai_hours_function(self):
        from modules.channel.voice.webhook_router import is_within_trai_hours

        # This tests the current time — it should return a bool
        result = is_within_trai_hours()
        assert isinstance(result, bool)


# ═══════════════════════════════════════════════════════════════════════════════
# Webhook Endpoint Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestVoiceWebhook:
    async def test_webhook_success(
        self, client: AsyncClient, voice_tenant: dict, voice_agent: dict,
    ):
        """Webhook receives valid payload, emits signals."""
        payload = _make_webhook_payload(phone=voice_agent["phone"])
        resp = await client.post(
            f"/api/v1/webhooks/voice/{voice_tenant['slug']}",
            json=payload,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "call_id" in data

    async def test_webhook_emits_signals(
        self, client: AsyncClient, voice_tenant: dict, voice_agent: dict,
    ):
        """Verify signals are actually stored in the database."""
        call_id = str(uuid.uuid4())
        payload = _make_webhook_payload(
            call_id=call_id,
            phone=voice_agent["phone"],
        )
        resp = await client.post(
            f"/api/v1/webhooks/voice/{voice_tenant['slug']}",
            json=payload,
        )
        assert resp.status_code == 200

        # Verify signals were created
        with sync_engine.begin() as conn:
            signals = conn.execute(
                text(
                    "SELECT signal_type, agent_id FROM signals "
                    "WHERE tenant_id = :tid AND agent_id = :aid "
                    "ORDER BY created_at"
                ),
                {
                    "tid": str(voice_tenant["id"]),
                    "aid": str(voice_agent["id"]),
                },
            ).fetchall()

        signal_types = [s[0] for s in signals]
        assert "voice_call_outcome" in signal_types
        assert "voice_conversation_analyzed" in signal_types

    async def test_webhook_with_recording_url(
        self, client: AsyncClient, voice_tenant: dict, voice_agent: dict,
    ):
        """Webhook with recording_url emits VOICE_CALL_RECORDING_STORED."""
        payload = _make_webhook_payload(
            phone=voice_agent["phone"],
            recording_url="https://storage.example.com/recording.mp3",
        )
        resp = await client.post(
            f"/api/v1/webhooks/voice/{voice_tenant['slug']}",
            json=payload,
        )
        assert resp.status_code == 200

        with sync_engine.begin() as conn:
            rec_signals = conn.execute(
                text(
                    "SELECT signal_type FROM signals "
                    "WHERE tenant_id = :tid AND signal_type = 'voice_call_recording_stored'"
                ),
                {"tid": str(voice_tenant["id"])},
            ).fetchall()
        assert len(rec_signals) >= 1

    async def test_webhook_unknown_tenant(self, client: AsyncClient):
        """Webhook for nonexistent tenant returns 404."""
        payload = _make_webhook_payload()
        resp = await client.post(
            "/api/v1/webhooks/voice/nonexistent-tenant-slug",
            json=payload,
        )
        assert resp.status_code == 404

    async def test_webhook_unknown_agent_phone(
        self, client: AsyncClient, voice_tenant: dict,
    ):
        """Webhook with unknown phone still succeeds (agent_id will be null)."""
        payload = _make_webhook_payload(phone="+910000000000")
        resp = await client.post(
            f"/api/v1/webhooks/voice/{voice_tenant['slug']}",
            json=payload,
        )
        assert resp.status_code == 200

    async def test_webhook_idempotency(
        self, client: AsyncClient, voice_tenant: dict, voice_agent: dict,
    ):
        """Duplicate webhook with same call_id doesn't create duplicate signals."""
        call_id = str(uuid.uuid4())
        payload = _make_webhook_payload(
            call_id=call_id,
            phone=voice_agent["phone"],
        )

        # Send twice
        resp1 = await client.post(
            f"/api/v1/webhooks/voice/{voice_tenant['slug']}",
            json=payload,
        )
        resp2 = await client.post(
            f"/api/v1/webhooks/voice/{voice_tenant['slug']}",
            json=payload,
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200

        # Check signal count — should have exactly 2 (outcome + analyzed), not 4
        with sync_engine.begin() as conn:
            count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM signals "
                    "WHERE tenant_id = :tid AND agent_id = :aid"
                ),
                {
                    "tid": str(voice_tenant["id"]),
                    "aid": str(voice_agent["id"]),
                },
            ).scalar()
        # Idempotency keys prevent duplicates
        assert count == 2

    async def test_webhook_nlu_dormancy_extraction(
        self, client: AsyncClient, voice_tenant: dict, voice_agent: dict,
    ):
        """Webhook with dormancy-indicating transcript produces correct NLU extraction."""
        payload = _make_webhook_payload(
            phone=voice_agent["phone"],
            transcript="Commission bahut kam hai, LIC mein zyada milta hai",
            sentiment="negative",
        )
        resp = await client.post(
            f"/api/v1/webhooks/voice/{voice_tenant['slug']}",
            json=payload,
        )
        assert resp.status_code == 200

        # Check the analyzed signal payload
        with sync_engine.begin() as conn:
            analyzed = conn.execute(
                text(
                    "SELECT payload FROM signals "
                    "WHERE tenant_id = :tid AND signal_type = 'voice_conversation_analyzed' "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"tid": str(voice_tenant["id"])},
            ).scalar()

        assert analyzed is not None
        assert "commission_too_low" in str(analyzed.get("dormancy_reasons_detected", []))
        assert "lic" in str(analyzed.get("competitor_mentions", []))
        assert analyzed.get("commission_concerns") is True

    async def test_webhook_different_outcomes(
        self, client: AsyncClient, voice_tenant: dict, voice_agent: dict,
    ):
        """Different call outcomes are correctly parsed."""
        for outcome in ["answered", "busy", "no_answer", "switched_off"]:
            # Use unique call_id for each to avoid idempotency
            payload = _make_webhook_payload(
                call_id=str(uuid.uuid4()),
                phone=voice_agent["phone"],
                outcome=outcome,
            )
            resp = await client.post(
                f"/api/v1/webhooks/voice/{voice_tenant['slug']}",
                json=payload,
            )
            assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# Tenant Isolation Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestVoiceTenantIsolation:
    async def test_webhook_signals_isolated(self, client: AsyncClient):
        """Signals from tenant A webhook don't appear in tenant B."""
        t1_id, t2_id = uuid.uuid4(), uuid.uuid4()
        t1_slug = f"viso-a-{t1_id.hex[:6]}"
        t2_slug = f"viso-b-{t2_id.hex[:6]}"

        with sync_engine.begin() as conn:
            for tid, slug in [(t1_id, t1_slug), (t2_id, t2_slug)]:
                conn.execute(
                    text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
                    {"id": str(tid), "name": f"Tenant {slug}", "slug": slug},
                )

        try:
            # Send webhook to tenant A
            payload = _make_webhook_payload()
            resp = await client.post(
                f"/api/v1/webhooks/voice/{t1_slug}",
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

        finally:
            with sync_engine.begin() as conn:
                conn.execute(text("DELETE FROM signals WHERE tenant_id IN (:t1, :t2)"),
                             {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM tenants WHERE id IN (:t1, :t2)"),
                             {"t1": str(t1_id), "t2": str(t2_id)})


# ═══════════════════════════════════════════════════════════════════════════════
# Tenant Slug Lookup Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestTenantSlugLookup:
    async def test_get_tenant_by_slug_exists(self):
        from modules.tenant import service as tenant_service
        from config.database import async_session_factory

        tid = uuid.uuid4()
        slug = f"slug-{tid.hex[:8]}"
        with sync_engine.begin() as conn:
            conn.execute(
                text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
                {"id": str(tid), "name": f"Tenant {slug}", "slug": slug},
            )
        try:
            async with async_session_factory() as session:
                tenant = await tenant_service.get_tenant_by_slug(session, slug)
                assert tenant is not None
                assert tenant.id == tid
        finally:
            with sync_engine.begin() as conn:
                conn.execute(text("DELETE FROM tenants WHERE id = :tid"), {"tid": str(tid)})

    async def test_get_tenant_by_slug_not_found(self):
        from modules.tenant import service as tenant_service
        from config.database import async_session_factory

        async with async_session_factory() as session:
            tenant = await tenant_service.get_tenant_by_slug(session, "nonexistent-slug-xyz")
            assert tenant is None
