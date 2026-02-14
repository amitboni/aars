"""modules/integration/commission_adapter.py — Commission System adapter.

Emits COMMISSION_CREDITED signals.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import SignalSource, SignalType
from modules.agent.models import Agent
from modules.integration.base import IntegrationAdapter
from modules.signal.schemas import SignalEmit


class CommissionAdapter(IntegrationAdapter):
    """Handles commission credit data — emits COMMISSION_CREDITED signals."""

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

        payload = {
            "amount": float(row.get("amount", 0)),
            "credit_date": row.get("credit_date", ""),
        }
        if row.get("policy_number"):
            payload["policy_number"] = row["policy_number"]
        if row.get("commission_type"):
            payload["commission_type"] = row["commission_type"]

        return [
            SignalEmit(
                signal_type=SignalType.COMMISSION_CREDITED,
                source=SignalSource.COMMISSION_SYNC,
                agent_id=agent.id,
                payload=payload,
                idempotency_key=self.get_idempotency_key(row),
            )
        ]

    def get_idempotency_key(self, row: dict) -> str:
        agent_code = row.get("agent_code", "")
        credit_date = row.get("credit_date", "")
        policy_number = row.get("policy_number", "")
        return f"commission_sync:{agent_code}:{credit_date}:{policy_number}"

    def validate_row(self, row: dict) -> tuple[bool, list[str]]:
        errors = []
        if not row.get("agent_code"):
            errors.append("agent_code is required")
        if not row.get("amount"):
            errors.append("amount is required")
        if not row.get("credit_date"):
            errors.append("credit_date is required")
        return (len(errors) == 0, errors)
