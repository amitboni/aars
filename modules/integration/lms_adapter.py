"""modules/integration/lms_adapter.py — License Management System adapter.

Handles:
- Training completions: emits TRAINING_COMPLETED_EXTERNAL signals
- License status changes: emits LICENSE_STATUS_CHANGED signals
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import SignalSource, SignalType
from modules.agent.models import Agent
from modules.integration.base import IntegrationAdapter
from modules.signal.schemas import SignalEmit


class LMSTrainingAdapter(IntegrationAdapter):
    """Handles training completion data from LMS."""

    async def process_row(
        self, row: dict, tenant_id: uuid.UUID, db: AsyncSession
    ) -> list[SignalEmit]:
        agent_code = row.get("agent_code", "").strip()

        result = await db.execute(
            select(Agent).where(
                Agent.tenant_id == tenant_id,
                Agent.agent_code == agent_code,
                Agent.deleted_at.is_(None),
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:
            return []

        # Spec 3.6.2: training_history fields
        payload = {
            "training_name": row.get("training_name", ""),
            "completion_date": row.get("completion_date", ""),
            "status": row.get("status", "completed"),
        }
        if row.get("score") is not None:
            payload["score"] = float(row["score"])
        if row.get("hours") is not None:
            payload["hours"] = float(row["hours"])

        return [
            SignalEmit(
                signal_type=SignalType.TRAINING_COMPLETED_EXTERNAL,
                source=SignalSource.LMS_SYNC,
                agent_id=agent.id,
                payload=payload,
                idempotency_key=self.get_idempotency_key(row),
            )
        ]

    def get_idempotency_key(self, row: dict) -> str:
        agent_code = row.get("agent_code", "")
        training_name = row.get("training_name", "")
        completion_date = row.get("completion_date", "")
        return f"lms_sync:{agent_code}:{training_name}:{completion_date}"

    def validate_row(self, row: dict) -> tuple[bool, list[str]]:
        errors = []
        if not row.get("agent_code"):
            errors.append("agent_code is required")
        if not row.get("training_name"):
            errors.append("training_name is required")
        if not row.get("completion_date"):
            errors.append("completion_date is required")
        return (len(errors) == 0, errors)


class LMSLicenseAdapter(IntegrationAdapter):
    """Handles license status change data from LMS."""

    async def process_row(
        self, row: dict, tenant_id: uuid.UUID, db: AsyncSession
    ) -> list[SignalEmit]:
        agent_code = row.get("agent_code", "").strip()

        result = await db.execute(
            select(Agent).where(
                Agent.tenant_id == tenant_id,
                Agent.agent_code == agent_code,
                Agent.deleted_at.is_(None),
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:
            return []

        # Spec 3.6.2: license_management fields
        payload = {
            "license_number": row.get("license_number", ""),
            "status": row.get("status", ""),
        }
        if row.get("expiry_date"):
            payload["expiry_date"] = row["expiry_date"]
        if row.get("training_hours_completed") is not None:
            payload["training_hours_completed"] = float(row["training_hours_completed"])

        return [
            SignalEmit(
                signal_type=SignalType.LICENSE_STATUS_CHANGED,
                source=SignalSource.LMS_SYNC,
                agent_id=agent.id,
                payload=payload,
                idempotency_key=self.get_idempotency_key(row),
            )
        ]

    def get_idempotency_key(self, row: dict) -> str:
        agent_code = row.get("agent_code", "")
        license_number = row.get("license_number", "")
        status = row.get("status", "")
        return f"lms_sync:{agent_code}:{license_number}:{status}"

    def validate_row(self, row: dict) -> tuple[bool, list[str]]:
        errors = []
        if not row.get("agent_code"):
            errors.append("agent_code is required")
        if not row.get("license_number"):
            errors.append("license_number is required")
        if not row.get("status"):
            errors.append("status is required")
        return (len(errors) == 0, errors)
