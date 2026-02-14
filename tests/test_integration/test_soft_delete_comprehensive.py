"""tests/test_integration/test_soft_delete_comprehensive.py — Soft delete tests.

Verifies:
- Soft deleted agents are excluded from all queries
- Soft deleted playbooks are excluded from triggers and lists
- Soft deleted records still exist in DB
- Soft deleted agent's signals still exist (append-only)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

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
from modules.playbook.schemas import PlaybookCreate, PlaybookStepCreate
from modules.playbook import service as playbook_service


@pytest.fixture
async def sd_db():
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        yield session
        await session.commit()


class TestSoftDeleteAgent:
    """Agent soft delete tests."""

    @pytest.mark.asyncio
    async def test_soft_deleted_agent_excluded_from_list(self, test_tenant, sd_db):
        """Soft-deleted agent is excluded from list queries."""
        db = sd_db
        tenant_id = test_tenant["id"]

        agent = await agent_service.create_agent(db, tenant_id, AgentCreate(
            agent_code="SD-AGENT-001", full_name="Soft Delete Agent", phone="9876543100",
        ))
        await db.commit()

        # Verify agent appears in list
        agents, _ = await agent_service.list_agents(db, tenant_id)
        assert any(a.id == agent.id for a in agents)

        # Soft delete
        agent.deleted_at = datetime.now(timezone.utc)
        await db.flush()
        await db.commit()

        # Verify agent is excluded from list
        agents, _ = await agent_service.list_agents(db, tenant_id)
        assert not any(a.id == agent.id for a in agents)

    @pytest.mark.asyncio
    async def test_soft_deleted_agent_excluded_from_get(self, test_tenant, sd_db):
        """Soft-deleted agent raises NotFoundError on get."""
        db = sd_db
        tenant_id = test_tenant["id"]

        agent = await agent_service.create_agent(db, tenant_id, AgentCreate(
            agent_code="SD-AGENT-002", full_name="Soft Delete Agent 2", phone="9876543101",
        ))
        agent.deleted_at = datetime.now(timezone.utc)
        await db.flush()
        await db.commit()

        from core.exceptions import NotFoundError
        with pytest.raises(NotFoundError):
            await agent_service.get_agent(db, agent.id, tenant_id)

    @pytest.mark.asyncio
    async def test_soft_deleted_agent_still_in_db(self, test_tenant, sd_db):
        """Soft-deleted agent still exists in the database."""
        db = sd_db
        tenant_id = test_tenant["id"]

        agent = await agent_service.create_agent(db, tenant_id, AgentCreate(
            agent_code="SD-AGENT-003", full_name="Soft Delete Agent 3", phone="9876543102",
        ))
        agent.deleted_at = datetime.now(timezone.utc)
        await db.flush()
        await db.commit()

        # Direct query without soft delete filter
        result = await db.execute(
            select(Agent).where(Agent.id == agent.id)
        )
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.deleted_at is not None

    @pytest.mark.asyncio
    async def test_soft_deleted_agent_signals_preserved(self, test_tenant, sd_db):
        """Signals for a soft-deleted agent still exist (append-only)."""
        db = sd_db
        tenant_id = test_tenant["id"]

        agent = await agent_service.create_agent(db, tenant_id, AgentCreate(
            agent_code="SD-AGENT-004", full_name="Soft Delete Agent 4", phone="9876543103",
        ))
        await db.commit()

        # Emit signal
        signal, _ = await signal_service.emit_signal(db, tenant_id, SignalEmit(
            signal_type=SignalType.POLICY_SOLD,
            source=SignalSource.PAS_SYNC,
            agent_id=agent.id,
            payload={"policy_number": "SD-POL-001"},
        ))
        await db.commit()

        # Soft delete agent
        agent.deleted_at = datetime.now(timezone.utc)
        await db.flush()
        await db.commit()

        # Signal still exists
        result = await db.execute(
            select(Signal).where(Signal.id == signal.id)
        )
        found_signal = result.scalar_one_or_none()
        assert found_signal is not None
        assert found_signal.signal_type == SignalType.POLICY_SOLD


class TestSoftDeletePlaybook:
    """Playbook soft delete tests."""

    @pytest.mark.asyncio
    async def test_soft_deleted_playbook_excluded_from_list(self, test_tenant, sd_db):
        """Soft-deleted playbook excluded from list."""
        db = sd_db
        tenant_id = test_tenant["id"]

        pb = await playbook_service.create_playbook(db, tenant_id, PlaybookCreate(
            name="SD Playbook",
            steps=[PlaybookStepCreate(step_number=1, name="Step 1", action_type="whatsapp_message")],
        ))
        await db.commit()

        # Verify it appears
        playbooks, _ = await playbook_service.list_playbooks(db, tenant_id)
        assert any(p.id == pb.id for p in playbooks)

        # Soft delete
        await playbook_service.delete_playbook(db, pb.id, tenant_id)
        await db.commit()

        # Verify excluded
        playbooks, _ = await playbook_service.list_playbooks(db, tenant_id)
        assert not any(p.id == pb.id for p in playbooks)

    @pytest.mark.asyncio
    async def test_soft_deleted_playbook_cannot_be_triggered(self, test_tenant, sd_db):
        """Soft-deleted playbook raises NotFoundError when triggered."""
        db = sd_db
        tenant_id = test_tenant["id"]

        pb = await playbook_service.create_playbook(db, tenant_id, PlaybookCreate(
            name="SD Playbook Trigger",
            steps=[PlaybookStepCreate(step_number=1, name="Step 1", action_type="whatsapp_message")],
        ))
        agent = await agent_service.create_agent(db, tenant_id, AgentCreate(
            agent_code="SD-PB-AGENT", full_name="PB Agent", phone="9876543110",
        ))
        await db.commit()

        # Soft delete
        await playbook_service.delete_playbook(db, pb.id, tenant_id)
        await db.commit()

        from modules.playbook.schemas import PlaybookTrigger
        from core.exceptions import NotFoundError
        with pytest.raises(NotFoundError):
            await playbook_service.trigger_playbook(db, tenant_id, PlaybookTrigger(
                playbook_id=pb.id, agent_id=agent.id,
            ))
