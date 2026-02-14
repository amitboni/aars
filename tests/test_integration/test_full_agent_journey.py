"""tests/test_integration/test_full_agent_journey.py — The FULL JOURNEY test.

Tests the complete agent lifecycle:
  onboard → licensed → first_sale → active
  Also: dormant → voice call → playbook → training → ADM nudge → sale → celebration
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text

from config.database import async_engine, sync_engine
from core.enums import SignalSource, SignalType
from modules.agent.models import Agent
from modules.agent.schemas import AgentCreate
from modules.agent import service as agent_service
from modules.signal.models import Signal
from modules.signal.schemas import SignalEmit
from modules.signal import service as signal_service
from modules.signal.processor import process_signal
from modules.playbook.models import Playbook, PlaybookStep, PlaybookRun
from modules.playbook.schemas import PlaybookCreate, PlaybookStepCreate, PlaybookTrigger
from modules.playbook import service as playbook_service
from modules.decision.engine import evaluate_agent


@pytest.fixture
def journey_tenant(test_tenant):
    """A tenant with config for the journey test."""
    return test_tenant


@pytest.fixture
async def journey_db():
    """Async session for the journey test."""
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        yield session
        await session.commit()


class TestFullAgentJourney:
    """The most important test in the system — full agent lifecycle."""

    @pytest.mark.asyncio
    async def test_onboard_to_active_journey(self, journey_tenant, journey_db):
        """Test: onboard → licensed → first_sale → active."""
        db = journey_db
        tenant_id = journey_tenant["id"]

        # 1. Create agent (ONBOARDED)
        agent = await agent_service.create_agent(db, tenant_id, AgentCreate(
            agent_code="JOURNEY-001",
            full_name="Journey Agent",
            phone="9876543210",
            lifecycle_state="onboarded",
        ))
        await db.commit()
        assert agent.lifecycle_state == "onboarded"

        # 2. Agent gets licensed → emit LICENSE_STATUS_CHANGED
        sig_data = SignalEmit(
            signal_type=SignalType.LICENSE_STATUS_CHANGED,
            source=SignalSource.LMS_SYNC,
            agent_id=agent.id,
            payload={"new_status": "ACTIVE", "license_number": "IRDAI-TEST-001"},
            idempotency_key="journey:license:001",
        )
        signal, created = await signal_service.emit_signal(db, tenant_id, sig_data)
        assert created
        await process_signal(db, signal)
        await db.commit()

        await db.refresh(agent)
        assert agent.lifecycle_state == "licensed"

        # 3. Agent makes FIRST sale → POLICY_SOLD
        sig_data = SignalEmit(
            signal_type=SignalType.POLICY_SOLD,
            source=SignalSource.PAS_SYNC,
            agent_id=agent.id,
            payload={"policy_number": "POL-JOURNEY-001", "premium_amount": 15000},
            idempotency_key="journey:policy:001",
        )
        signal, created = await signal_service.emit_signal(db, tenant_id, sig_data)
        await process_signal(db, signal)
        await db.commit()

        await db.refresh(agent)
        assert agent.lifecycle_state == "first_sale"
        assert agent.total_policies_sold == 1

        # 4. Agent makes SECOND sale → transitions to ACTIVE
        sig_data = SignalEmit(
            signal_type=SignalType.POLICY_SOLD,
            source=SignalSource.PAS_SYNC,
            agent_id=agent.id,
            payload={"policy_number": "POL-JOURNEY-002", "premium_amount": 20000},
            idempotency_key="journey:policy:002",
        )
        signal, created = await signal_service.emit_signal(db, tenant_id, sig_data)
        await process_signal(db, signal)
        await db.commit()

        await db.refresh(agent)
        assert agent.lifecycle_state == "active"
        assert agent.total_policies_sold == 2

        # Verify signal chain exists
        result = await db.execute(
            select(Signal).where(
                Signal.agent_id == agent.id,
                Signal.tenant_id == tenant_id,
            ).order_by(Signal.created_at)
        )
        signals = list(result.scalars().all())
        signal_types = [s.signal_type for s in signals]

        assert SignalType.LICENSE_STATUS_CHANGED in signal_types
        assert SignalType.POLICY_SOLD in signal_types
        assert SignalType.LIFECYCLE_STATE_CHANGED in signal_types

    @pytest.mark.asyncio
    async def test_dormant_reactivation_journey(self, journey_tenant, journey_db):
        """Test: dormant → voice call → reason identified → playbook → training → sale → active."""
        db = journey_db
        tenant_id = journey_tenant["id"]

        # 1. Create dormant agent
        agent = await agent_service.create_agent(db, tenant_id, AgentCreate(
            agent_code="JOURNEY-DORMANT-001",
            full_name="Dormant Agent",
            phone="9876543211",
            lifecycle_state="dormant",
        ))
        agent.dormancy_reason = "training_gap.product_knowledge_insufficient"
        agent.engagement_score = 10.0
        await db.flush()
        await db.commit()

        # 2. Voice call with answered outcome → positive signal, triggers re-engagement
        sig_data = SignalEmit(
            signal_type=SignalType.VOICE_CALL_OUTCOME,
            source=SignalSource.VOICE_AI,
            agent_id=agent.id,
            payload={"outcome": "answered", "duration_seconds": 180},
            channel="voice_ai",
            idempotency_key="journey:voice:dormant:001",
        )
        signal, created = await signal_service.emit_signal(db, tenant_id, sig_data)
        await process_signal(db, signal)
        await db.commit()

        await db.refresh(agent)
        # Dormant + positive signal → should transition to licensed
        assert agent.lifecycle_state == "licensed"
        assert agent.dormancy_reason is None  # cleared on exit from dormant

        # 3. WhatsApp training interaction → agent watches training
        sig_data = SignalEmit(
            signal_type=SignalType.WHATSAPP_TRAINING_INTERACTION,
            source=SignalSource.WHATSAPP_BOT,
            agent_id=agent.id,
            payload={"completion_percentage": 80, "interaction_type": "VIDEO_WATCHED"},
            channel="whatsapp_bot",
            idempotency_key="journey:training:001",
        )
        signal, created = await signal_service.emit_signal(db, tenant_id, sig_data)
        await process_signal(db, signal)
        await db.commit()

        await db.refresh(agent)
        assert agent.last_positive_signal_at is not None

        # 4. ADM logs a call (positive engagement)
        sig_data = SignalEmit(
            signal_type=SignalType.ADM_AGENT_CALL_LOGGED,
            source=SignalSource.ADM_REPORT,
            agent_id=agent.id,
            payload={"outcome": "DETAILED_DISCUSSION", "notes": "Discussed product training"},
            idempotency_key="journey:adm_call:001",
        )
        signal, created = await signal_service.emit_signal(db, tenant_id, sig_data)
        await process_signal(db, signal)
        await db.commit()

        # 5. Agent makes a sale → POLICY_SOLD → transitions to first_sale
        sig_data = SignalEmit(
            signal_type=SignalType.POLICY_SOLD,
            source=SignalSource.PAS_SYNC,
            agent_id=agent.id,
            payload={"policy_number": "POL-REACTIVATED-001", "premium_amount": 12000},
            idempotency_key="journey:policy:reactivated:001",
        )
        signal, created = await signal_service.emit_signal(db, tenant_id, sig_data)
        await process_signal(db, signal)
        await db.commit()

        await db.refresh(agent)
        assert agent.lifecycle_state == "first_sale"
        assert agent.total_policies_sold == 1

        # 6. Second sale → ACTIVE
        sig_data = SignalEmit(
            signal_type=SignalType.POLICY_SOLD,
            source=SignalSource.PAS_SYNC,
            agent_id=agent.id,
            payload={"policy_number": "POL-REACTIVATED-002", "premium_amount": 18000},
            idempotency_key="journey:policy:reactivated:002",
        )
        signal, created = await signal_service.emit_signal(db, tenant_id, sig_data)
        await process_signal(db, signal)
        await db.commit()

        await db.refresh(agent)
        assert agent.lifecycle_state == "active"

        # Verify full signal chain
        result = await db.execute(
            select(Signal).where(
                Signal.agent_id == agent.id,
                Signal.tenant_id == tenant_id,
            ).order_by(Signal.created_at)
        )
        signals = list(result.scalars().all())
        assert len(signals) >= 6  # At least 6 signals + lifecycle change signals

    @pytest.mark.asyncio
    async def test_license_expiry_lapsed_journey(self, journey_tenant, journey_db):
        """Test: active agent → license expires → LAPSED → license renewed → LICENSED."""
        db = journey_db
        tenant_id = journey_tenant["id"]

        # Create active agent
        agent = await agent_service.create_agent(db, tenant_id, AgentCreate(
            agent_code="JOURNEY-LAPSE-001",
            full_name="Lapse Agent",
            phone="9876543212",
            lifecycle_state="active",
        ))
        agent.total_policies_sold = 5
        await db.flush()
        await db.commit()

        # License expires
        sig_data = SignalEmit(
            signal_type=SignalType.LICENSE_STATUS_CHANGED,
            source=SignalSource.LMS_SYNC,
            agent_id=agent.id,
            payload={"new_status": "EXPIRED"},
            idempotency_key="journey:license:lapse:001",
        )
        signal, _ = await signal_service.emit_signal(db, tenant_id, sig_data)
        await process_signal(db, signal)
        await db.commit()

        await db.refresh(agent)
        assert agent.lifecycle_state == "lapsed"

        # License renewed
        sig_data = SignalEmit(
            signal_type=SignalType.LICENSE_STATUS_CHANGED,
            source=SignalSource.LMS_SYNC,
            agent_id=agent.id,
            payload={"new_status": "ACTIVE"},
            idempotency_key="journey:license:renew:001",
        )
        signal, _ = await signal_service.emit_signal(db, tenant_id, sig_data)
        await process_signal(db, signal)
        await db.commit()

        await db.refresh(agent)
        assert agent.lifecycle_state == "licensed"

    @pytest.mark.asyncio
    async def test_signal_idempotency(self, journey_tenant, journey_db):
        """Test: same signal with same idempotency_key is not duplicated."""
        db = journey_db
        tenant_id = journey_tenant["id"]

        agent = await agent_service.create_agent(db, tenant_id, AgentCreate(
            agent_code="JOURNEY-IDEMP-001",
            full_name="Idempotent Agent",
            phone="9876543213",
        ))
        await db.commit()

        key = "journey:idemp:policy:001"
        sig_data = SignalEmit(
            signal_type=SignalType.POLICY_SOLD,
            source=SignalSource.PAS_SYNC,
            agent_id=agent.id,
            payload={"policy_number": "POL-IDEMP-001"},
            idempotency_key=key,
        )

        # First emit — created
        signal1, created1 = await signal_service.emit_signal(db, tenant_id, sig_data)
        await db.commit()
        assert created1 is True

        # Second emit — not created, returns existing
        signal2, created2 = await signal_service.emit_signal(db, tenant_id, sig_data)
        assert created2 is False
        assert signal1.id == signal2.id
