"""modules/training/router.py — Training API endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_role
from modules.training import service
from modules.training.schemas import (
    QuizCreate,
    QuizResponse,
    TrainingModuleCreate,
    TrainingModuleResponse,
    TrainingModuleSummaryResponse,
    TrainingModuleUpdate,
    TrainingProgressCreate,
    TrainingProgressResponse,
    TrainingProgressUpdate,
)

router = APIRouter(prefix="/api/v1", tags=["training"])


# ─── Training Module CRUD ────────────────────────────────────────────────────

@router.post(
    "/training/modules",
    response_model=TrainingModuleResponse,
    status_code=201,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def create_module(
    data: TrainingModuleCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    module = await service.create_module(db, user["tenant_id"], data)
    return TrainingModuleResponse.model_validate(module)


@router.get(
    "/training/modules",
    dependencies=[Depends(require_role("super_admin", "tenant_admin", "regional_manager", "adm"))],
)
async def list_modules(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    cursor: uuid.UUID | None = Query(None),
    topic: str | None = Query(None),
    difficulty: str | None = Query(None),
    is_active: bool | None = Query(None),
):
    modules, next_cursor = await service.list_modules(
        db, user["tenant_id"], limit, cursor,
        topic=topic,
        difficulty=difficulty,
        is_active=is_active,
    )
    return {
        "data": [TrainingModuleSummaryResponse.model_validate(m) for m in modules],
        "next_cursor": str(next_cursor) if next_cursor else None,
        "has_more": next_cursor is not None,
    }


@router.get(
    "/training/modules/{module_id}",
    response_model=TrainingModuleResponse,
    dependencies=[Depends(require_role("super_admin", "tenant_admin", "regional_manager", "adm"))],
)
async def get_module(
    module_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    module = await service.get_module(db, module_id, user["tenant_id"])
    return TrainingModuleResponse.model_validate(module)


@router.put(
    "/training/modules/{module_id}",
    response_model=TrainingModuleResponse,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def update_module(
    module_id: uuid.UUID,
    data: TrainingModuleUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    module = await service.update_module(db, module_id, user["tenant_id"], data)
    return TrainingModuleResponse.model_validate(module)


@router.delete(
    "/training/modules/{module_id}",
    status_code=204,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def delete_module(
    module_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    await service.delete_module(db, module_id, user["tenant_id"])
    return None


@router.post(
    "/training/modules/{module_id}/upload",
    response_model=TrainingModuleResponse,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def upload_media(
    module_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    content = await file.read()
    module = await service.upload_media(
        db, module_id, user["tenant_id"],
        file_data=content,
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
    )
    return TrainingModuleResponse.model_validate(module)


# ─── Quiz ────────────────────────────────────────────────────────────────────

@router.put(
    "/training/modules/{module_id}/quiz",
    response_model=QuizResponse,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def create_or_update_quiz(
    module_id: uuid.UUID,
    data: QuizCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    quiz = await service.create_or_update_quiz(db, module_id, user["tenant_id"], data)
    return QuizResponse.model_validate(quiz)


@router.get(
    "/training/modules/{module_id}/quiz",
    response_model=QuizResponse,
    dependencies=[Depends(require_role("super_admin", "tenant_admin", "regional_manager", "adm"))],
)
async def get_quiz(
    module_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    quiz = await service.get_quiz(db, module_id, user["tenant_id"])
    return QuizResponse.model_validate(quiz)


# ─── Training Progress ──────────────────────────────────────────────────────

@router.get(
    "/training/progress",
    dependencies=[Depends(require_role("super_admin", "tenant_admin", "regional_manager", "adm"))],
)
async def list_progress(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    cursor: uuid.UUID | None = Query(None),
    agent_id: uuid.UUID | None = Query(None),
    module_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None),
):
    progress_list, next_cursor = await service.list_progress(
        db, user["tenant_id"], limit, cursor,
        agent_id=agent_id,
        module_id=module_id,
        status=status,
    )
    return {
        "data": [TrainingProgressResponse.model_validate(p) for p in progress_list],
        "next_cursor": str(next_cursor) if next_cursor else None,
        "has_more": next_cursor is not None,
    }


@router.post(
    "/training/progress",
    response_model=TrainingProgressResponse,
    status_code=201,
    dependencies=[Depends(require_role("super_admin", "tenant_admin", "adm"))],
)
async def assign_module(
    data: TrainingProgressCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    progress = await service.assign_module(
        db, user["tenant_id"],
        module_id=data.training_module_id,
        agent_id=data.agent_id,
        assigned_by=data.assigned_by,
        playbook_run_id=data.playbook_run_id,
    )
    return TrainingProgressResponse.model_validate(progress)


@router.put(
    "/training/progress/{progress_id}",
    response_model=TrainingProgressResponse,
    dependencies=[Depends(require_role("super_admin", "tenant_admin"))],
)
async def update_progress(
    progress_id: uuid.UUID,
    data: TrainingProgressUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    progress = await service.update_progress(db, progress_id, user["tenant_id"], data)
    return TrainingProgressResponse.model_validate(progress)
