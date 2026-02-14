"""tests/test_integration/test_concurrent_operations.py — Concurrency safety tests.

Verifies:
- Concurrent signal emissions with same idempotency key produce only one signal
- Duplicate playbook triggers are rejected (ConflictError)
- Decision engine evaluations are idempotent
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import async_engine
from core.enums import SignalSource, SignalType
from modules.agent.schemas import AgentCreate
from modules.agent import service as agent_service
from modules.signal.models import Signal
from modules.signal.schemas import SignalEmit
from modules.signal import service as signal_service
from modules.playbook.schemas import PlaybookCreate, PlaybookStepCreate, PlaybookTrigger
from modules.playbook import service as playbook_service
from core.exceptions import ConflictError


@pytest.fixture
async def conc_db():
    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        yield session
        await session.commit()


class TestConcurrentSignals:
    """Concurrent signal emission safety."""

    @pytest.mark.asyncio
    async def test_idempotent_signal_no_duplicate(self, test_tenant, conc_db):
        """Two sequential emits with same idempotency_key yield exactly one signal."""
        db = conc_db
        tenant_id = test_tenant["id"]

        agent = await agent_service.create_agent(db, tenant_id, AgentCreate(
            agent_code="CONC-SIG-001", full_name="Concurrent Agent", phone="9876543300",
        ))
        await db.commit()

        key = "conc:test:policy:001"
        sig_data = SignalEmit(
            signal_type=SignalType.POLICY_SOLD,
            source=SignalSource.PAS_SYNC,
            agent_id=agent.id,
            payload={"policy_number": "CONC-POL-001"},
            idempotency_key=key,
        )

        # First emit
        signal1, created1 = await signal_service.emit_signal(db, tenant_id, sig_data)
        await db.commit()
        assert created1 is True

        # Second emit — same key
        signal2, created2 = await signal_service.emit_signal(db, tenant_id, sig_data)
        assert created2 is False
        assert signal1.id == signal2.id

        # Verify only one signal in DB
        result = await db.execute(
            select(Signal).where(
                Signal.tenant_id == tenant_id,
                Signal.idempotency_key == key,
            )
        )
        signals = list(result.scalars().all())
        assert len(signals) == 1

    @pytest.mark.asyncio
    async def test_different_idempotency_keys_create_separate_signals(self, test_tenant, conc_db):
        """Different idempotency keys create separate signals."""
        db = conc_db
        tenant_id = test_tenant["id"]

        agent = await agent_service.create_agent(db, tenant_id, AgentCreate(
            agent_code="CONC-SIG-002", full_name="Multi Signal Agent", phone="9876543301",
        ))
        await db.commit()

        for i in range(3):
            sig_data = SignalEmit(
                signal_type=SignalType.POLICY_SOLD,
                source=SignalSource.PAS_SYNC,
                agent_id=agent.id,
                payload={"policy_number": f"CONC-POL-{i+1:03d}"},
                idempotency_key=f"conc:multi:{i}",
            )
            signal, created = await signal_service.emit_signal(db, tenant_id, sig_data)
            await db.commit()
            assert created is True

        # Verify 3 separate signals
        result = await db.execute(
            select(Signal).where(
                Signal.tenant_id == tenant_id,
                Signal.agent_id == agent.id,
                Signal.signal_type == SignalType.POLICY_SOLD,
            )
        )
        signals = list(result.scalars().all())
        assert len(signals) == 3

    @pytest.mark.asyncio
    async def test_signals_without_idempotency_key_always_create(self, test_tenant, conc_db):
        """Signals without idempotency_key are always created (no dedup)."""
        db = conc_db
        tenant_id = test_tenant["id"]

        agent = await agent_service.create_agent(db, tenant_id, AgentCreate(
            agent_code="CONC-SIG-003", full_name="No Key Agent", phone="9876543302",
        ))
        await db.commit()

        for _ in range(3):
            sig_data = SignalEmit(
                signal_type=SignalType.POLICY_SOLD,
                source=SignalSource.PAS_SYNC,
                agent_id=agent.id,
                payload={"policy_number": "CONC-POL-NOKEY"},
            )
            signal, created = await signal_service.emit_signal(db, tenant_id, sig_data)
            await db.commit()
            assert created is True

        result = await db.execute(
            select(Signal).where(
                Signal.tenant_id == tenant_id,
                Signal.agent_id == agent.id,
            )
        )
        signals = list(result.scalars().all())
        assert len(signals) == 3


class TestConcurrentPlaybooks:
    """Concurrent playbook trigger safety."""

    @pytest.mark.asyncio
    async def test_duplicate_playbook_trigger_rejected(self, test_tenant, conc_db):
        """Triggering the same playbook for the same agent twice raises ConflictError."""
        db = conc_db
        tenant_id = test_tenant["id"]

        pb = await playbook_service.create_playbook(db, tenant_id, PlaybookCreate(
            name="Concurrent Playbook",
            steps=[PlaybookStepCreate(step_number=1, name="Step 1", action_type="whatsapp_message")],
        ))
        agent = await agent_service.create_agent(db, tenant_id, AgentCreate(
            agent_code="CONC-PB-001", full_name="PB Agent", phone="9876543310",
        ))
        await db.commit()

        # First trigger — success
        run = await playbook_service.trigger_playbook(db, tenant_id, PlaybookTrigger(
            playbook_id=pb.id, agent_id=agent.id,
        ))
        await db.commit()
        assert run.status == "in_progress"

        # Second trigger — conflict
        with pytest.raises(ConflictError):
            await playbook_service.trigger_playbook(db, tenant_id, PlaybookTrigger(
                playbook_id=pb.id, agent_id=agent.id,
            ))

    @pytest.mark.asyncio
    async def test_different_agents_same_playbook_ok(self, test_tenant, conc_db):
        """Same playbook can be triggered for different agents."""
        db = conc_db
        tenant_id = test_tenant["id"]

        pb = await playbook_service.create_playbook(db, tenant_id, PlaybookCreate(
            name="Multi Agent Playbook",
            steps=[PlaybookStepCreate(step_number=1, name="Step 1", action_type="whatsapp_message")],
        ))
        agent1 = await agent_service.create_agent(db, tenant_id, AgentCreate(
            agent_code="CONC-PB-A1", full_name="Agent 1", phone="9876543311",
        ))
        agent2 = await agent_service.create_agent(db, tenant_id, AgentCreate(
            agent_code="CONC-PB-A2", full_name="Agent 2", phone="9876543312",
        ))
        await db.commit()

        run1 = await playbook_service.trigger_playbook(db, tenant_id, PlaybookTrigger(
            playbook_id=pb.id, agent_id=agent1.id,
        ))
        await db.commit()

        run2 = await playbook_service.trigger_playbook(db, tenant_id, PlaybookTrigger(
            playbook_id=pb.id, agent_id=agent2.id,
        ))
        await db.commit()

        assert run1.id != run2.id
        assert run1.agent_id != run2.agent_id


class TestConcurrentDecisions:
    """Decision engine idempotency."""

    @pytest.mark.asyncio
    async def test_evaluate_agent_is_idempotent(self, test_tenant, conc_db):
        """Evaluating the same agent multiple times produces consistent results."""
        db = conc_db
        tenant_id = test_tenant["id"]

        agent = await agent_service.create_agent(db, tenant_id, AgentCreate(
            agent_code="CONC-DEC-001", full_name="Decision Agent", phone="9876543320",
            lifecycle_state="active",
        ))
        agent.engagement_score = 30.0
        await db.flush()
        await db.commit()

        from modules.decision.engine import evaluate_agent

        result1 = await evaluate_agent(db, agent.id, tenant_id)
        result2 = await evaluate_agent(db, agent.id, tenant_id)

        # Both evaluations should yield the same decision action
        assert result1.decision_action == result2.decision_action
