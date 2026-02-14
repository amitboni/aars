"""modules/playbook/service.py — Playbook CRUD and run management."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import SignalType
from core.exceptions import ConflictError, NotFoundError, ValidationError
from modules.playbook.models import (
    Playbook,
    PlaybookRun,
    PlaybookStep,
    PlaybookStepRun,
)
from modules.playbook.schemas import PlaybookCreate, PlaybookUpdate, PlaybookTrigger
from modules.signal.models import Signal

logger = logging.getLogger(__name__)


# ─── Playbook CRUD ───────────────────────────────────────────────────────────

async def create_playbook(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: PlaybookCreate,
) -> Playbook:
    """Create a new playbook with its steps."""
    # Check for duplicate name within tenant
    existing = await db.execute(
        select(Playbook).where(
            Playbook.tenant_id == tenant_id,
            Playbook.name == data.name,
            Playbook.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(
            f"Playbook with name '{data.name}' already exists",
            details={"name": data.name},
        )

    playbook = Playbook(
        tenant_id=tenant_id,
        name=data.name,
        description=data.description,
        trigger_conditions=data.trigger_conditions,
        success_criteria=data.success_criteria,
        max_duration_days=data.max_duration_days,
    )
    db.add(playbook)
    await db.flush()

    # Create steps
    for step_data in data.steps:
        step = PlaybookStep(
            playbook_id=playbook.id,
            step_number=step_data.step_number,
            name=step_data.name,
            action_type=step_data.action_type,
            action_config=step_data.action_config,
            delay_days=step_data.delay_days,
            next_step_rules=step_data.next_step_rules,
        )
        db.add(step)

    await db.flush()
    # Refresh to load steps relationship
    await db.refresh(playbook)
    return playbook


async def get_playbook(
    db: AsyncSession,
    playbook_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Playbook:
    result = await db.execute(
        select(Playbook).where(
            Playbook.id == playbook_id,
            Playbook.tenant_id == tenant_id,
            Playbook.deleted_at.is_(None),
        )
    )
    playbook = result.scalar_one_or_none()
    if not playbook:
        raise NotFoundError("Playbook", playbook_id)
    return playbook


async def update_playbook(
    db: AsyncSession,
    playbook_id: uuid.UUID,
    tenant_id: uuid.UUID,
    data: PlaybookUpdate,
) -> Playbook:
    playbook = await get_playbook(db, playbook_id, tenant_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(playbook, field, value)
    await db.flush()
    return playbook


async def list_playbooks(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 50,
    cursor: uuid.UUID | None = None,
    is_active: bool | None = None,
) -> tuple[list[Playbook], uuid.UUID | None]:
    """List playbooks with cursor-based pagination."""
    query = (
        select(Playbook)
        .where(Playbook.tenant_id == tenant_id, Playbook.deleted_at.is_(None))
        .order_by(Playbook.created_at.desc(), Playbook.id)
        .limit(limit + 1)
    )
    if is_active is not None:
        query = query.where(Playbook.is_active == is_active)

    if cursor:
        cursor_pb = await db.get(Playbook, cursor)
        if cursor_pb:
            query = query.where(
                (Playbook.created_at < cursor_pb.created_at)
                | ((Playbook.created_at == cursor_pb.created_at) & (Playbook.id > cursor_pb.id))
            )

    result = await db.execute(query)
    playbooks = list(result.scalars().all())

    next_cursor = None
    if len(playbooks) > limit:
        playbooks = playbooks[:limit]
        next_cursor = playbooks[-1].id

    return playbooks, next_cursor


# ─── Playbook Runs ───────────────────────────────────────────────────────────

async def trigger_playbook(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: PlaybookTrigger,
) -> PlaybookRun:
    """Start a playbook run for an agent."""
    # Validate playbook exists
    playbook = await get_playbook(db, data.playbook_id, tenant_id)
    if not playbook.is_active:
        raise ValidationError("Cannot trigger an inactive playbook")

    if not playbook.steps:
        raise ValidationError("Playbook has no steps defined")

    # Check for existing active run of this playbook for this agent
    existing_run = await db.execute(
        select(PlaybookRun).where(
            PlaybookRun.playbook_id == data.playbook_id,
            PlaybookRun.agent_id == data.agent_id,
            PlaybookRun.tenant_id == tenant_id,
            PlaybookRun.status == "in_progress",
        )
    )
    if existing_run.scalar_one_or_none():
        raise ConflictError(
            "This playbook is already running for this agent",
            details={"playbook_id": str(data.playbook_id), "agent_id": str(data.agent_id)},
        )

    # Compute first step's due time
    first_step = playbook.steps[0]
    now = datetime.now(timezone.utc)
    next_due = now + timedelta(days=first_step.delay_days)

    run = PlaybookRun(
        tenant_id=tenant_id,
        playbook_id=data.playbook_id,
        agent_id=data.agent_id,
        status="in_progress",
        current_step_number=first_step.step_number,
        context=data.context,
        started_at=now,
        next_step_due_at=next_due,
    )
    db.add(run)
    await db.flush()

    # Increment execution counter
    playbook.times_executed = (playbook.times_executed or 0) + 1

    # Emit PLAYBOOK_STARTED signal
    signal = Signal(
        tenant_id=tenant_id,
        signal_type=SignalType.PLAYBOOK_STARTED,
        source="system",
        agent_id=data.agent_id,
        timestamp=now,
        payload={
            "playbook_id": str(data.playbook_id),
            "playbook_name": playbook.name,
            "trigger_reason": data.context.get("trigger_reason", "manual"),
            "steps_count": len(playbook.steps),
        },
        metadata_={},
        processed=True,
        processed_at=now,
    )
    db.add(signal)
    await db.flush()

    return run


async def get_playbook_run(
    db: AsyncSession,
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> PlaybookRun:
    result = await db.execute(
        select(PlaybookRun).where(
            PlaybookRun.id == run_id,
            PlaybookRun.tenant_id == tenant_id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise NotFoundError("PlaybookRun", run_id)
    return run


async def delete_playbook(
    db: AsyncSession,
    playbook_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Playbook:
    """Soft-delete a playbook."""
    playbook = await get_playbook(db, playbook_id, tenant_id)
    playbook.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    return playbook


async def list_playbook_runs(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 50,
    cursor: uuid.UUID | None = None,
    agent_id: uuid.UUID | None = None,
    status: str | None = None,
) -> tuple[list[PlaybookRun], uuid.UUID | None]:
    query = (
        select(PlaybookRun)
        .where(PlaybookRun.tenant_id == tenant_id)
        .order_by(PlaybookRun.created_at.desc(), PlaybookRun.id)
        .limit(limit + 1)
    )
    if agent_id:
        query = query.where(PlaybookRun.agent_id == agent_id)
    if status:
        query = query.where(PlaybookRun.status == status)

    if cursor:
        cursor_run = await db.get(PlaybookRun, cursor)
        if cursor_run:
            query = query.where(
                (PlaybookRun.created_at < cursor_run.created_at)
                | ((PlaybookRun.created_at == cursor_run.created_at) & (PlaybookRun.id > cursor_run.id))
            )

    result = await db.execute(query)
    runs = list(result.scalars().all())

    next_cursor = None
    if len(runs) > limit:
        runs = runs[:limit]
        next_cursor = runs[-1].id

    return runs, next_cursor
