"""tests/test_integration/test_tenant_isolation_comprehensive.py — Tenant isolation tests.

Creates 2 tenants. All operations on tenant A must be invisible to tenant B.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from config.database import async_engine, sync_engine
from core.enums import SignalSource, SignalType
from modules.agent.models import Agent
from modules.agent.schemas import AgentCreate
from modules.agent import service as agent_service
from modules.signal.schemas import SignalEmit
from modules.signal import service as signal_service
from modules.playbook.schemas import PlaybookCreate, PlaybookStepCreate
from modules.playbook import service as playbook_service


@pytest.fixture
def tenant_a():
    """Create tenant A."""
    tenant_id = uuid.uuid4()
    slug = f"iso-a-{tenant_id.hex[:8]}"
    with sync_engine.begin() as conn:
        conn.execute(
            text("INSERT INTO tenants (id, name, slug, subscription_tier, is_active, config) "
                 "VALUES (:id, :name, :slug, 'trial', true, '{}'::jsonb)"),
            {"id": str(tenant_id), "name": f"Tenant A {slug}", "slug": slug},
        )
    yield {"id": tenant_id, "slug": slug}
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM signals WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM playbook_steps WHERE playbook_id IN (SELECT id FROM playbooks WHERE tenant_id = :tid)"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM playbooks WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM agents WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM tenants WHERE id = :tid"), {"tid": str(tenant_id)})


@pytest.fixture
def tenant_b():
    """Create tenant B."""
    tenant_id = uuid.uuid4()
    slug = f"iso-b-{tenant_id.hex[:8]}"
    with sync_engine.begin() as conn:
        conn.execute(
            text("INSERT INTO tenants (id, name, slug, subscription_tier, is_active, config) "
                 "VALUES (:id, :name, :slug, 'trial', true, '{}'::jsonb)"),
            {"id": str(tenant_id), "name": f"Tenant B {slug}", "slug": slug},
        )
    yield {"id": tenant_id, "slug": slug}
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM signals WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM playbook_steps WHERE playbook_id IN (SELECT id FROM playbooks WHERE tenant_id = :tid)"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM playbooks WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM agents WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        conn.execute(text("DELETE FROM tenants WHERE id = :tid"), {"tid": str(tenant_id)})


@pytest.fixture
async def iso_db():
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        yield session
        await session.commit()


class TestTenantIsolation:
    """Comprehensive tenant isolation tests."""

    @pytest.mark.asyncio
    async def test_agents_isolated(self, tenant_a, tenant_b, iso_db):
        """Agents created in tenant A are invisible to tenant B."""
        db = iso_db

        # Create agents in both tenants
        agent_a = await agent_service.create_agent(db, tenant_a["id"], AgentCreate(
            agent_code="ISO-A-001", full_name="Agent A", phone="9876543001",
        ))
        agent_b = await agent_service.create_agent(db, tenant_b["id"], AgentCreate(
            agent_code="ISO-B-001", full_name="Agent B", phone="9876543002",
        ))
        await db.commit()

        # List agents for each tenant
        agents_a, _ = await agent_service.list_agents(db, tenant_a["id"])
        agents_b, _ = await agent_service.list_agents(db, tenant_b["id"])

        agent_a_ids = {a.id for a in agents_a}
        agent_b_ids = {a.id for a in agents_b}

        assert agent_a.id in agent_a_ids
        assert agent_a.id not in agent_b_ids
        assert agent_b.id in agent_b_ids
        assert agent_b.id not in agent_a_ids

    @pytest.mark.asyncio
    async def test_signals_isolated(self, tenant_a, tenant_b, iso_db):
        """Signals in tenant A are invisible to tenant B."""
        db = iso_db

        agent_a = await agent_service.create_agent(db, tenant_a["id"], AgentCreate(
            agent_code="ISO-SIG-A", full_name="Signal Agent A", phone="9876543011",
        ))
        agent_b = await agent_service.create_agent(db, tenant_b["id"], AgentCreate(
            agent_code="ISO-SIG-B", full_name="Signal Agent B", phone="9876543012",
        ))
        await db.commit()

        # Emit signals for each
        await signal_service.emit_signal(db, tenant_a["id"], SignalEmit(
            signal_type=SignalType.POLICY_SOLD, source=SignalSource.PAS_SYNC,
            agent_id=agent_a.id, payload={"policy_number": "ISO-A-POL-001"},
        ))
        await signal_service.emit_signal(db, tenant_b["id"], SignalEmit(
            signal_type=SignalType.POLICY_SOLD, source=SignalSource.PAS_SYNC,
            agent_id=agent_b.id, payload={"policy_number": "ISO-B-POL-001"},
        ))
        await db.commit()

        # Query signals by tenant
        signals_a, _ = await signal_service.list_signals(db, tenant_a["id"])
        signals_b, _ = await signal_service.list_signals(db, tenant_b["id"])

        signal_agent_ids_a = {s.agent_id for s in signals_a}
        signal_agent_ids_b = {s.agent_id for s in signals_b}

        assert agent_a.id in signal_agent_ids_a
        assert agent_a.id not in signal_agent_ids_b

    @pytest.mark.asyncio
    async def test_playbooks_isolated(self, tenant_a, tenant_b, iso_db):
        """Playbooks in tenant A are invisible to tenant B."""
        db = iso_db

        pb_a = await playbook_service.create_playbook(db, tenant_a["id"], PlaybookCreate(
            name="Isolation Test A",
            steps=[PlaybookStepCreate(
                step_number=1, name="Step 1", action_type="whatsapp_message",
            )],
        ))
        pb_b = await playbook_service.create_playbook(db, tenant_b["id"], PlaybookCreate(
            name="Isolation Test B",
            steps=[PlaybookStepCreate(
                step_number=1, name="Step 1", action_type="whatsapp_message",
            )],
        ))
        await db.commit()

        playbooks_a, _ = await playbook_service.list_playbooks(db, tenant_a["id"])
        playbooks_b, _ = await playbook_service.list_playbooks(db, tenant_b["id"])

        pb_a_ids = {p.id for p in playbooks_a}
        pb_b_ids = {p.id for p in playbooks_b}

        assert pb_a.id in pb_a_ids
        assert pb_a.id not in pb_b_ids

    @pytest.mark.asyncio
    async def test_cross_tenant_agent_lookup_returns_404(self, tenant_a, tenant_b, iso_db):
        """Getting an agent from the wrong tenant raises NotFoundError."""
        db = iso_db

        agent_a = await agent_service.create_agent(db, tenant_a["id"], AgentCreate(
            agent_code="ISO-XREF-A", full_name="Cross Ref Agent", phone="9876543021",
        ))
        await db.commit()

        from core.exceptions import NotFoundError
        with pytest.raises(NotFoundError):
            await agent_service.get_agent(db, agent_a.id, tenant_b["id"])

    @pytest.mark.asyncio
    async def test_same_agent_code_different_tenants(self, tenant_a, tenant_b, iso_db):
        """Same agent_code can exist in different tenants."""
        db = iso_db

        agent_a = await agent_service.create_agent(db, tenant_a["id"], AgentCreate(
            agent_code="SHARED-CODE", full_name="Agent A", phone="9876543031",
        ))
        agent_b = await agent_service.create_agent(db, tenant_b["id"], AgentCreate(
            agent_code="SHARED-CODE", full_name="Agent B", phone="9876543032",
        ))
        await db.commit()

        assert agent_a.id != agent_b.id
        assert agent_a.agent_code == agent_b.agent_code
