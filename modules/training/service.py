"""modules/training/service.py — Training module CRUD and operations."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConflictError, NotFoundError, ValidationError
from modules.training.models import TrainingModule, TrainingQuiz, TrainingProgress
from modules.training.schemas import (
    TrainingModuleCreate,
    TrainingModuleUpdate,
    QuizCreate,
    TrainingProgressUpdate,
)

logger = logging.getLogger(__name__)


# ─── Training Module CRUD ────────────────────────────────────────────────────

async def create_module(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: TrainingModuleCreate,
) -> TrainingModule:
    """Create a new training module."""
    module = TrainingModule(
        tenant_id=tenant_id,
        title=data.title,
        description=data.description,
        topic=data.topic,
        difficulty=data.difficulty,
        duration_minutes=data.duration_minutes,
        language=data.language,
        content_type=data.content_type,
        file_url=data.file_url,
        expires_at=data.expires_at,
    )
    db.add(module)
    await db.flush()
    return module


async def get_module(
    db: AsyncSession,
    module_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> TrainingModule:
    result = await db.execute(
        select(TrainingModule).where(
            TrainingModule.id == module_id,
            TrainingModule.tenant_id == tenant_id,
            TrainingModule.deleted_at.is_(None),
        )
    )
    module = result.scalar_one_or_none()
    if not module:
        raise NotFoundError("TrainingModule", module_id)
    return module


async def list_modules(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 50,
    cursor: uuid.UUID | None = None,
    topic: str | None = None,
    difficulty: str | None = None,
    is_active: bool | None = None,
) -> tuple[list[TrainingModule], uuid.UUID | None]:
    """List training modules with cursor-based pagination."""
    query = (
        select(TrainingModule)
        .where(TrainingModule.tenant_id == tenant_id, TrainingModule.deleted_at.is_(None))
        .order_by(TrainingModule.created_at.desc(), TrainingModule.id)
        .limit(limit + 1)
    )
    if topic:
        query = query.where(TrainingModule.topic == topic)
    if difficulty:
        query = query.where(TrainingModule.difficulty == difficulty)
    if is_active is not None:
        query = query.where(TrainingModule.is_active == is_active)

    if cursor:
        cursor_mod = await db.get(TrainingModule, cursor)
        if cursor_mod:
            query = query.where(
                (TrainingModule.created_at < cursor_mod.created_at)
                | (
                    (TrainingModule.created_at == cursor_mod.created_at)
                    & (TrainingModule.id > cursor_mod.id)
                )
            )

    result = await db.execute(query)
    modules = list(result.scalars().all())

    next_cursor = None
    if len(modules) > limit:
        modules = modules[:limit]
        next_cursor = modules[-1].id

    return modules, next_cursor


async def update_module(
    db: AsyncSession,
    module_id: uuid.UUID,
    tenant_id: uuid.UUID,
    data: TrainingModuleUpdate,
) -> TrainingModule:
    module = await get_module(db, module_id, tenant_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(module, field, value)
    await db.flush()
    return module


async def delete_module(
    db: AsyncSession,
    module_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> TrainingModule:
    """Soft-delete a training module."""
    module = await get_module(db, module_id, tenant_id)
    module.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    return module


async def upload_media(
    db: AsyncSession,
    module_id: uuid.UUID,
    tenant_id: uuid.UUID,
    file_data: bytes,
    filename: str,
    content_type: str = "application/octet-stream",
) -> TrainingModule:
    """Upload media file to S3 and store the key on the module."""
    from config.s3 import upload_file, ensure_bucket
    from config.settings import settings

    module = await get_module(db, module_id, tenant_id)

    bucket = settings.S3_BUCKET_TRAINING
    await ensure_bucket(bucket)

    key = f"{tenant_id}/{module_id}/{filename}"
    await upload_file(bucket, key, file_data, content_type)

    module.file_key = key
    module.file_size_bytes = len(file_data)
    await db.flush()
    return module


# ─── Quiz ────────────────────────────────────────────────────────────────────

async def create_or_update_quiz(
    db: AsyncSession,
    module_id: uuid.UUID,
    tenant_id: uuid.UUID,
    data: QuizCreate,
) -> TrainingQuiz:
    """Upsert quiz for a training module."""
    # Validate module exists and belongs to tenant
    await get_module(db, module_id, tenant_id)

    result = await db.execute(
        select(TrainingQuiz).where(TrainingQuiz.training_module_id == module_id)
    )
    quiz = result.scalar_one_or_none()

    if quiz:
        quiz.questions = data.questions
        quiz.passing_score = data.passing_score
        quiz.max_attempts = data.max_attempts
    else:
        quiz = TrainingQuiz(
            training_module_id=module_id,
            questions=data.questions,
            passing_score=data.passing_score,
            max_attempts=data.max_attempts,
        )
        db.add(quiz)

    await db.flush()
    return quiz


async def get_quiz(
    db: AsyncSession,
    module_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> TrainingQuiz:
    """Get quiz for a training module."""
    # Validate module exists and belongs to tenant
    await get_module(db, module_id, tenant_id)

    result = await db.execute(
        select(TrainingQuiz).where(TrainingQuiz.training_module_id == module_id)
    )
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise NotFoundError("TrainingQuiz", module_id)
    return quiz


# ─── Training Progress ──────────────────────────────────────────────────────

async def list_progress(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 50,
    cursor: uuid.UUID | None = None,
    agent_id: uuid.UUID | None = None,
    module_id: uuid.UUID | None = None,
    status: str | None = None,
) -> tuple[list[TrainingProgress], uuid.UUID | None]:
    """List training progress records with cursor-based pagination."""
    query = (
        select(TrainingProgress)
        .where(TrainingProgress.tenant_id == tenant_id)
        .order_by(TrainingProgress.created_at.desc(), TrainingProgress.id)
        .limit(limit + 1)
    )
    if agent_id:
        query = query.where(TrainingProgress.agent_id == agent_id)
    if module_id:
        query = query.where(TrainingProgress.training_module_id == module_id)
    if status:
        query = query.where(TrainingProgress.status == status)

    if cursor:
        cursor_prog = await db.get(TrainingProgress, cursor)
        if cursor_prog:
            query = query.where(
                (TrainingProgress.created_at < cursor_prog.created_at)
                | (
                    (TrainingProgress.created_at == cursor_prog.created_at)
                    & (TrainingProgress.id > cursor_prog.id)
                )
            )

    result = await db.execute(query)
    progress_list = list(result.scalars().all())

    next_cursor = None
    if len(progress_list) > limit:
        progress_list = progress_list[:limit]
        next_cursor = progress_list[-1].id

    return progress_list, next_cursor


async def assign_module(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    module_id: uuid.UUID,
    agent_id: uuid.UUID,
    assigned_by: str = "system",
    playbook_run_id: uuid.UUID | None = None,
) -> TrainingProgress:
    """Assign a training module to an agent. Creates a progress record."""
    # Validate module exists
    module = await get_module(db, module_id, tenant_id)

    progress = TrainingProgress(
        tenant_id=tenant_id,
        training_module_id=module_id,
        agent_id=agent_id,
        status="assigned",
        assigned_by=assigned_by,
        playbook_run_id=playbook_run_id,
    )
    db.add(progress)

    # Increment assignment counter
    module.times_assigned = (module.times_assigned or 0) + 1

    await db.flush()
    return progress


async def update_progress(
    db: AsyncSession,
    progress_id: uuid.UUID,
    tenant_id: uuid.UUID,
    data: TrainingProgressUpdate,
) -> TrainingProgress:
    result = await db.execute(
        select(TrainingProgress).where(
            TrainingProgress.id == progress_id,
            TrainingProgress.tenant_id == tenant_id,
        )
    )
    progress = result.scalar_one_or_none()
    if not progress:
        raise NotFoundError("TrainingProgress", progress_id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(progress, field, value)
    await db.flush()
    return progress
