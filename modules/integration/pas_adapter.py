"""modules/integration/pas_adapter.py — Policy Admin System adapter.

Handles two data types:
- Agent master data: creates/updates agents via agent_service
- Policy transactions: emits POLICY_SOLD signals
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import SignalSource, SignalType
from modules.agent.models import Agent
from modules.agent.schemas import AgentCreate
from modules.agent import service as agent_service
from modules.integration.base import IntegrationAdapter
from modules.signal.schemas import SignalEmit

import re

_PHONE_RE = re.compile(r"^[6-9]\d{9}$")


def _validate_phone(phone: str) -> bool:
    """Validate Indian mobile phone number (10 digits starting with 6-9)."""
    cleaned = phone.strip()
    # Remove country code prefix (not lstrip — that strips chars, not prefix)
    if cleaned.startswith("+91"):
        cleaned = cleaned[3:]
    elif cleaned.startswith("91") and len(cleaned) > 10:
        cleaned = cleaned[2:]
    cleaned = cleaned.lstrip("0")
    return bool(_PHONE_RE.match(cleaned))


class PASAgentAdapter(IntegrationAdapter):
    """Handles agent master data from PAS — creates/updates agents."""

    async def process_row(
        self, row: dict, tenant_id: uuid.UUID, db: AsyncSession
    ) -> list[SignalEmit]:
        agent_code = row.get("agent_code", "").strip()
        if not agent_code:
            return []

        # Check if agent already exists
        result = await db.execute(
            select(Agent).where(
                Agent.tenant_id == tenant_id,
                Agent.agent_code == agent_code,
                Agent.deleted_at.is_(None),
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing agent fields (spec 3.6.2: agent_master fields)
            updatable = (
                "full_name", "phone", "email", "license_number",
                "preferred_language", "license_expiry_date",
            )
            for field in updatable:
                if row.get(field):
                    setattr(existing, field, row[field])
            # Handle adm_assignment → assigned_adm_id (UUID lookup deferred)
            if row.get("assigned_adm_id"):
                existing.assigned_adm_id = uuid.UUID(row["assigned_adm_id"])
            # Handle region → region_node_id (UUID lookup deferred)
            if row.get("region_node_id"):
                existing.region_node_id = uuid.UUID(row["region_node_id"])
            await db.flush()
            agent_id = existing.id
        else:
            # Create new agent (spec 3.6.2: all agent_master fields)
            agent_data = AgentCreate(
                agent_code=agent_code,
                full_name=row.get("full_name", agent_code),
                phone=row.get("phone", "0000000000"),
                email=row.get("email"),
                lifecycle_state=row.get("lifecycle_state", "onboarded"),
                license_number=row.get("license_number"),
                preferred_language=row.get("preferred_language", "hi"),
                assigned_adm_id=uuid.UUID(row["assigned_adm_id"]) if row.get("assigned_adm_id") else None,
                region_node_id=uuid.UUID(row["region_node_id"]) if row.get("region_node_id") else None,
            )
            agent = await agent_service.create_agent(db, tenant_id, agent_data)
            agent_id = agent.id

        # Emit AGENT_DATA_UPDATED signal
        payload = {"agent_code": agent_code, "import_type": "agent_master"}
        if row.get("onboarding_date"):
            payload["onboarding_date"] = row["onboarding_date"]

        return [
            SignalEmit(
                signal_type=SignalType.AGENT_DATA_UPDATED,
                source=SignalSource.PAS_SYNC,
                agent_id=agent_id,
                payload=payload,
                idempotency_key=self.get_idempotency_key(row),
            )
        ]

    def get_idempotency_key(self, row: dict) -> str:
        agent_code = row.get("agent_code", "")
        return f"pas_sync:{agent_code}:agent_data_updated"

    def validate_row(self, row: dict) -> tuple[bool, list[str]]:
        errors = []
        if not row.get("agent_code"):
            errors.append("agent_code is required")
        phone = row.get("phone", "")
        if phone and not _validate_phone(phone):
            errors.append(f"Invalid phone number: {phone}")
        return (len(errors) == 0, errors)


class PASPolicyAdapter(IntegrationAdapter):
    """Handles policy transaction data from PAS — emits POLICY_SOLD signals."""

    async def process_row(
        self, row: dict, tenant_id: uuid.UUID, db: AsyncSession
    ) -> list[SignalEmit]:
        agent_code = row.get("agent_code", "").strip()
        policy_number = row.get("policy_number", "").strip()

        # Resolve agent_code to agent_id
        result = await db.execute(
            select(Agent).where(
                Agent.tenant_id == tenant_id,
                Agent.agent_code == agent_code,
                Agent.deleted_at.is_(None),
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:
            return []  # Skip — agent not found

        # Spec 3.6.2: policy_transactions fields
        payload = {"policy_number": policy_number}
        for str_field in ("product_name", "product_code", "policy_date", "status"):
            if row.get(str_field):
                payload[str_field] = row[str_field]
        for num_field in ("premium_amount", "sum_assured"):
            if row.get(num_field):
                payload[num_field] = float(row[num_field])

        return [
            SignalEmit(
                signal_type=SignalType.POLICY_SOLD,
                source=SignalSource.PAS_SYNC,
                agent_id=agent.id,
                payload=payload,
                idempotency_key=self.get_idempotency_key(row),
            )
        ]

    def get_idempotency_key(self, row: dict) -> str:
        policy_number = row.get("policy_number", "")
        return f"pas_sync:{policy_number}:policy_sold"

    def validate_row(self, row: dict) -> tuple[bool, list[str]]:
        errors = []
        if not row.get("agent_code"):
            errors.append("agent_code is required")
        if not row.get("policy_number"):
            errors.append("policy_number is required")
        return (len(errors) == 0, errors)
