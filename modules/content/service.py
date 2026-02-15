"""modules/content/service.py — Message template CRUD and operations."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConflictError, NotFoundError, ValidationError
from modules.content.models import MessageTemplate, TemplateUsageLog
from modules.content.schemas import TemplateCreate, TemplateUpdate


async def create_template(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: TemplateCreate,
) -> MessageTemplate:
    """Create a new message template with status=draft."""
    # Check for duplicate name+version within tenant
    existing = await db.execute(
        select(MessageTemplate).where(
            MessageTemplate.tenant_id == tenant_id,
            MessageTemplate.name == data.name,
            MessageTemplate.version == 1,
            MessageTemplate.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(
            f"Template with name '{data.name}' already exists in this tenant",
            details={"name": data.name},
        )

    template = MessageTemplate(
        tenant_id=tenant_id,
        name=data.name,
        category=data.category,
        description=data.description,
        language_variants=data.language_variants,
        placeholders=data.placeholders,
        buttons=data.buttons,
        meta_template_id=data.meta_template_id,
        status="draft",
        version=1,
    )
    db.add(template)
    await db.flush()
    return template


async def get_template(
    db: AsyncSession,
    template_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> MessageTemplate:
    result = await db.execute(
        select(MessageTemplate).where(
            MessageTemplate.id == template_id,
            MessageTemplate.tenant_id == tenant_id,
            MessageTemplate.deleted_at.is_(None),
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise NotFoundError("Template", template_id)
    return template


async def list_templates(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 50,
    cursor: uuid.UUID | None = None,
    category: str | None = None,
    status: str | None = None,
) -> tuple[list[MessageTemplate], uuid.UUID | None]:
    """List templates with cursor-based pagination and optional filters."""
    query = (
        select(MessageTemplate)
        .where(MessageTemplate.tenant_id == tenant_id, MessageTemplate.deleted_at.is_(None))
        .order_by(MessageTemplate.created_at.desc(), MessageTemplate.id)
        .limit(limit + 1)
    )
    if category:
        query = query.where(MessageTemplate.category == category)
    if status:
        query = query.where(MessageTemplate.status == status)

    if cursor:
        cursor_tmpl = await db.get(MessageTemplate, cursor)
        if cursor_tmpl:
            query = query.where(
                (MessageTemplate.created_at < cursor_tmpl.created_at)
                | (
                    (MessageTemplate.created_at == cursor_tmpl.created_at)
                    & (MessageTemplate.id > cursor_tmpl.id)
                )
            )

    result = await db.execute(query)
    templates = list(result.scalars().all())

    next_cursor = None
    if len(templates) > limit:
        templates = templates[:limit]
        next_cursor = templates[-1].id

    return templates, next_cursor


async def update_template(
    db: AsyncSession,
    template_id: uuid.UUID,
    tenant_id: uuid.UUID,
    data: TemplateUpdate,
) -> MessageTemplate:
    """Update a template by creating a NEW version (new row). Old version is preserved."""
    old = await get_template(db, template_id, tenant_id)

    update_data = data.model_dump(exclude_unset=True)

    new_template = MessageTemplate(
        tenant_id=tenant_id,
        name=update_data.get("name", old.name),
        category=update_data.get("category", old.category),
        description=update_data.get("description", old.description),
        language_variants=update_data.get("language_variants", old.language_variants),
        placeholders=update_data.get("placeholders", old.placeholders),
        buttons=update_data.get("buttons", old.buttons),
        meta_template_id=update_data.get("meta_template_id", old.meta_template_id),
        status="draft",
        version=old.version + 1,
        previous_version_id=old.id,
        is_default=old.is_default,
    )
    db.add(new_template)
    await db.flush()
    return new_template


async def delete_template(
    db: AsyncSession,
    template_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> MessageTemplate:
    """Soft-delete a template."""
    template = await get_template(db, template_id, tenant_id)
    template.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    return template


async def approve_template(
    db: AsyncSession,
    template_id: uuid.UUID,
    tenant_id: uuid.UUID,
    approved_by_user_id: uuid.UUID,
) -> MessageTemplate:
    """Move template status to approved."""
    template = await get_template(db, template_id, tenant_id)
    if template.status not in ("draft", "in_review"):
        raise ValidationError(
            f"Cannot approve template in status '{template.status}'",
            details={"current_status": template.status},
        )
    template.status = "approved"
    template.approved_by = approved_by_user_id
    template.approved_at = datetime.now(timezone.utc)
    await db.flush()
    return template


async def activate_template(
    db: AsyncSession,
    template_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> MessageTemplate:
    """Move template status to active. Only allowed if currently approved."""
    template = await get_template(db, template_id, tenant_id)
    if template.status != "approved":
        raise ValidationError(
            f"Cannot activate template in status '{template.status}' — must be approved first",
            details={"current_status": template.status},
        )
    template.status = "active"
    await db.flush()
    return template


async def archive_template(
    db: AsyncSession,
    template_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> MessageTemplate:
    """Move template status to archived."""
    template = await get_template(db, template_id, tenant_id)
    template.status = "archived"
    await db.flush()
    return template


async def get_template_versions(
    db: AsyncSession,
    template_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> list[MessageTemplate]:
    """List all versions of a template by following the version chain."""
    # Get the requested template first
    template = await get_template(db, template_id, tenant_id)

    # Find all templates with the same name in this tenant
    result = await db.execute(
        select(MessageTemplate)
        .where(
            MessageTemplate.tenant_id == tenant_id,
            MessageTemplate.name == template.name,
            MessageTemplate.deleted_at.is_(None),
        )
        .order_by(MessageTemplate.version.desc())
    )
    return list(result.scalars().all())


async def preview_template(
    db: AsyncSession,
    template_id: uuid.UUID,
    tenant_id: uuid.UUID,
    language: str,
    params: dict,
) -> tuple[str, list]:
    """Render a template with placeholder substitution. Returns (rendered_text, buttons)."""
    template = await get_template(db, template_id, tenant_id)

    body = template.language_variants.get(language)
    if body is None:
        # Fall back to Hindi
        body = template.language_variants.get("hi")
    if body is None:
        raise ValidationError(
            f"No language variant found for '{language}' or fallback 'hi'",
            details={"language": language},
        )

    # Substitute placeholders
    for key, value in params.items():
        body = body.replace(f"{{{key}}}", str(value))

    return body, template.buttons


async def get_active_template_by_name(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    name: str,
    language: str = "hi",
) -> tuple[MessageTemplate, str] | None:
    """Get the active template by name for runtime usage. Returns (template, rendered_body) or None."""
    result = await db.execute(
        select(MessageTemplate).where(
            MessageTemplate.tenant_id == tenant_id,
            MessageTemplate.name == name,
            MessageTemplate.status == "active",
            MessageTemplate.deleted_at.is_(None),
        )
        .order_by(MessageTemplate.version.desc())
        .limit(1)
    )
    template = result.scalar_one_or_none()
    if not template:
        return None

    body = template.language_variants.get(language)
    if body is None:
        body = template.language_variants.get("hi")
    if body is None:
        return None

    return template, body


async def log_template_usage(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
    version: int,
    agent_id: uuid.UUID,
    rendered: str,
    language: str,
    channel: str,
    playbook_run_id: uuid.UUID | None = None,
) -> TemplateUsageLog:
    """Create an audit log entry for template usage."""
    log = TemplateUsageLog(
        tenant_id=tenant_id,
        template_id=template_id,
        template_version=version,
        agent_id=agent_id,
        rendered_content=rendered,
        language_used=language,
        channel=channel,
        sent_at=datetime.now(timezone.utc),
        playbook_run_id=playbook_run_id,
    )
    db.add(log)
    await db.flush()
    return log
