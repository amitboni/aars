"""modules/agent/service.py — Agent CRUD operations."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConflictError, NotFoundError
from modules.agent.models import Agent
from modules.agent.schemas import AgentCreate, AgentUpdate


async def create_agent(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: AgentCreate,
) -> Agent:
    """Create a new agent within a tenant. Raises ConflictError if agent_code exists."""
    existing = await db.execute(
        select(Agent).where(
            Agent.tenant_id == tenant_id,
            Agent.agent_code == data.agent_code,
            Agent.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(
            f"Agent with code {data.agent_code} already exists in this tenant",
            details={"agent_code": data.agent_code},
        )

    agent = Agent(
        tenant_id=tenant_id,
        agent_code=data.agent_code,
        full_name=data.full_name.strip(),
        phone=data.phone,
        email=data.email,
        lifecycle_state=data.lifecycle_state,
        assigned_adm_id=data.assigned_adm_id,
        license_number=data.license_number,
        preferred_language=data.preferred_language,
        region_node_id=data.region_node_id,
    )
    db.add(agent)
    await db.flush()
    return agent


async def get_agent(db: AsyncSession, agent_id: uuid.UUID, tenant_id: uuid.UUID) -> Agent:
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.tenant_id == tenant_id,
            Agent.deleted_at.is_(None),
        )
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise NotFoundError("Agent", agent_id)
    return agent


async def get_agent_no_tenant_filter(db: AsyncSession, agent_id: uuid.UUID) -> Agent | None:
    """Get agent without tenant filter — used internally during signal processing."""
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def update_agent(
    db: AsyncSession, agent_id: uuid.UUID, tenant_id: uuid.UUID, data: AgentUpdate
) -> Agent:
    agent = await get_agent(db, agent_id, tenant_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(agent, field, value)
    await db.flush()
    return agent


async def list_agents(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 50,
    cursor: uuid.UUID | None = None,
    lifecycle_state: str | None = None,
    assigned_adm_id: uuid.UUID | None = None,
    region_node_id: uuid.UUID | None = None,
) -> tuple[list[Agent], uuid.UUID | None]:
    """List agents with cursor-based pagination and optional filters."""
    query = (
        select(Agent)
        .where(Agent.tenant_id == tenant_id, Agent.deleted_at.is_(None))
        .order_by(Agent.created_at.desc(), Agent.id)
        .limit(limit + 1)
    )
    if lifecycle_state:
        query = query.where(Agent.lifecycle_state == lifecycle_state)
    if assigned_adm_id:
        query = query.where(Agent.assigned_adm_id == assigned_adm_id)
    if region_node_id:
        query = query.where(Agent.region_node_id == region_node_id)

    if cursor:
        cursor_agent = await db.get(Agent, cursor)
        if cursor_agent:
            query = query.where(
                (Agent.created_at < cursor_agent.created_at)
                | ((Agent.created_at == cursor_agent.created_at) & (Agent.id > cursor_agent.id))
            )

    result = await db.execute(query)
    agents = list(result.scalars().all())

    next_cursor = None
    if len(agents) > limit:
        agents = agents[:limit]
        next_cursor = agents[-1].id

    return agents, next_cursor
