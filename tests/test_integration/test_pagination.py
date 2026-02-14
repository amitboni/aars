"""tests/test_integration/test_pagination.py — Cursor-based pagination tests.

Verifies all list endpoints paginate correctly using cursor-based pagination:
- limit+1 pattern returns correct page sizes
- next_cursor is None when no more pages
- Cursor navigation produces all records without duplicates
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import async_engine
from core.enums import SignalSource, SignalType
from modules.agent.schemas import AgentCreate
from modules.agent import service as agent_service
from modules.signal.schemas import SignalEmit
from modules.signal import service as signal_service
from modules.playbook.schemas import PlaybookCreate, PlaybookStepCreate
from modules.playbook import service as playbook_service


@pytest.fixture
async def page_db():
    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        yield session
        await session.commit()


class TestAgentPagination:
    """Agent list pagination tests."""

    @pytest.mark.asyncio
    async def test_single_page(self, test_tenant, page_db):
        """When total agents < limit, returns all with next_cursor=None."""
        db = page_db
        tenant_id = test_tenant["id"]

        for i in range(3):
            await agent_service.create_agent(db, tenant_id, AgentCreate(
                agent_code=f"PAGE-A-{i:03d}", full_name=f"Agent {i}", phone=f"98765430{i:02d}",
            ))
        await db.commit()

        agents, next_cursor = await agent_service.list_agents(db, tenant_id, limit=10)
        assert len(agents) == 3
        assert next_cursor is None

    @pytest.mark.asyncio
    async def test_multi_page(self, test_tenant, page_db):
        """When total agents > limit, paginate correctly."""
        db = page_db
        tenant_id = test_tenant["id"]

        for i in range(7):
            await agent_service.create_agent(db, tenant_id, AgentCreate(
                agent_code=f"PAGE-B-{i:03d}", full_name=f"Agent {i}", phone=f"98765431{i:02d}",
            ))
        await db.commit()

        # Page 1: limit=3
        page1, cursor1 = await agent_service.list_agents(db, tenant_id, limit=3)
        assert len(page1) == 3
        assert cursor1 is not None

        # Page 2
        page2, cursor2 = await agent_service.list_agents(db, tenant_id, limit=3, cursor=cursor1)
        assert len(page2) == 3
        assert cursor2 is not None

        # Page 3 (last page — only 1 remaining)
        page3, cursor3 = await agent_service.list_agents(db, tenant_id, limit=3, cursor=cursor2)
        assert len(page3) == 1
        assert cursor3 is None

        # All IDs unique
        all_ids = [a.id for a in page1 + page2 + page3]
        assert len(all_ids) == len(set(all_ids)) == 7

    @pytest.mark.asyncio
    async def test_filter_with_pagination(self, test_tenant, page_db):
        """Filtering by lifecycle_state still paginates correctly."""
        db = page_db
        tenant_id = test_tenant["id"]

        for i in range(4):
            await agent_service.create_agent(db, tenant_id, AgentCreate(
                agent_code=f"PAGE-C-ACT-{i:03d}", full_name=f"Active {i}",
                phone=f"98765432{i:02d}", lifecycle_state="active",
            ))
        for i in range(2):
            await agent_service.create_agent(db, tenant_id, AgentCreate(
                agent_code=f"PAGE-C-DOR-{i:03d}", full_name=f"Dormant {i}",
                phone=f"98765433{i:02d}", lifecycle_state="dormant",
            ))
        await db.commit()

        # Only active agents
        agents, cursor = await agent_service.list_agents(
            db, tenant_id, limit=10, lifecycle_state="active",
        )
        assert len(agents) == 4
        assert cursor is None

        # Paginate active with small limit
        page1, cursor1 = await agent_service.list_agents(
            db, tenant_id, limit=2, lifecycle_state="active",
        )
        assert len(page1) == 2
        assert cursor1 is not None

        page2, cursor2 = await agent_service.list_agents(
            db, tenant_id, limit=2, lifecycle_state="active", cursor=cursor1,
        )
        assert len(page2) == 2
        assert cursor2 is None

    @pytest.mark.asyncio
    async def test_empty_result(self, test_tenant, page_db):
        """No agents returns empty list and None cursor."""
        db = page_db
        tenant_id = test_tenant["id"]

        agents, cursor = await agent_service.list_agents(db, tenant_id, limit=10)
        assert agents == []
        assert cursor is None


class TestSignalPagination:
    """Signal list pagination tests."""

    @pytest.mark.asyncio
    async def test_signal_pagination(self, test_tenant, page_db):
        """Signals paginate correctly."""
        db = page_db
        tenant_id = test_tenant["id"]

        agent = await agent_service.create_agent(db, tenant_id, AgentCreate(
            agent_code="PAGE-SIG-001", full_name="Signal Agent", phone="9876543400",
        ))
        await db.commit()

        for i in range(5):
            await signal_service.emit_signal(db, tenant_id, SignalEmit(
                signal_type=SignalType.POLICY_SOLD,
                source=SignalSource.PAS_SYNC,
                agent_id=agent.id,
                payload={"policy_number": f"PAGE-POL-{i:03d}"},
            ))
            await db.commit()

        # Page 1
        page1, cursor1 = await signal_service.list_signals(db, tenant_id, limit=2)
        assert len(page1) == 2
        assert cursor1 is not None

        # Page 2
        page2, cursor2 = await signal_service.list_signals(db, tenant_id, limit=2, cursor=cursor1)
        assert len(page2) == 2
        assert cursor2 is not None

        # Page 3 (last)
        page3, cursor3 = await signal_service.list_signals(db, tenant_id, limit=2, cursor=cursor2)
        assert len(page3) == 1
        assert cursor3 is None

        all_ids = [s.id for s in page1 + page2 + page3]
        assert len(all_ids) == len(set(all_ids)) == 5

    @pytest.mark.asyncio
    async def test_signal_filter_by_type(self, test_tenant, page_db):
        """Signal filtering by type works with pagination."""
        db = page_db
        tenant_id = test_tenant["id"]

        agent = await agent_service.create_agent(db, tenant_id, AgentCreate(
            agent_code="PAGE-SIG-002", full_name="Filter Agent", phone="9876543401",
        ))
        await db.commit()

        # Emit mixed signals
        for i in range(3):
            await signal_service.emit_signal(db, tenant_id, SignalEmit(
                signal_type=SignalType.POLICY_SOLD,
                source=SignalSource.PAS_SYNC,
                agent_id=agent.id,
                payload={"policy_number": f"FILT-POL-{i}"},
            ))
        await signal_service.emit_signal(db, tenant_id, SignalEmit(
            signal_type=SignalType.LICENSE_STATUS_CHANGED,
            source=SignalSource.LMS_SYNC,
            agent_id=agent.id,
            payload={"new_status": "ACTIVE"},
        ))
        await db.commit()

        # Only POLICY_SOLD
        signals, _ = await signal_service.list_signals(
            db, tenant_id, signal_type=SignalType.POLICY_SOLD,
        )
        assert len(signals) == 3
        assert all(s.signal_type == SignalType.POLICY_SOLD for s in signals)


class TestPlaybookPagination:
    """Playbook list pagination tests."""

    @pytest.mark.asyncio
    async def test_playbook_pagination(self, test_tenant, page_db):
        """Playbooks paginate correctly."""
        db = page_db
        tenant_id = test_tenant["id"]

        for i in range(5):
            await playbook_service.create_playbook(db, tenant_id, PlaybookCreate(
                name=f"Page Playbook {i}",
                steps=[PlaybookStepCreate(
                    step_number=1, name="Step 1", action_type="whatsapp_message",
                )],
            ))
        await db.commit()

        # Page 1
        page1, cursor1 = await playbook_service.list_playbooks(db, tenant_id, limit=2)
        assert len(page1) == 2
        assert cursor1 is not None

        # Page 2
        page2, cursor2 = await playbook_service.list_playbooks(db, tenant_id, limit=2, cursor=cursor1)
        assert len(page2) == 2
        assert cursor2 is not None

        # Page 3
        page3, cursor3 = await playbook_service.list_playbooks(db, tenant_id, limit=2, cursor=cursor2)
        assert len(page3) == 1
        assert cursor3 is None

        all_ids = [p.id for p in page1 + page2 + page3]
        assert len(all_ids) == len(set(all_ids)) == 5

    @pytest.mark.asyncio
    async def test_playbook_soft_deleted_excluded_from_pagination(self, test_tenant, page_db):
        """Soft-deleted playbooks don't appear in paginated results."""
        db = page_db
        tenant_id = test_tenant["id"]

        pbs = []
        for i in range(3):
            pb = await playbook_service.create_playbook(db, tenant_id, PlaybookCreate(
                name=f"Del Playbook {i}",
                steps=[PlaybookStepCreate(
                    step_number=1, name="Step 1", action_type="whatsapp_message",
                )],
            ))
            pbs.append(pb)
        await db.commit()

        # Delete one
        await playbook_service.delete_playbook(db, pbs[1].id, tenant_id)
        await db.commit()

        playbooks, cursor = await playbook_service.list_playbooks(db, tenant_id, limit=10)
        assert len(playbooks) == 2
        assert pbs[1].id not in {p.id for p in playbooks}
        assert cursor is None
