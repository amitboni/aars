"""modules/integration/base.py — Abstract adapter interface for integration adapters."""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from modules.signal.schemas import SignalEmit


class AdapterType(StrEnum):
    """Integration adapter types per spec 3.6.1."""
    REALTIME_API = "realtime_api"
    BATCH_FILE = "batch_file"
    WEBHOOK = "webhook"
    MANUAL_UPLOAD = "manual_upload"
    DATABASE_SYNC = "database_sync"


class IntegrationAdapter(ABC):
    """Base class for all integration adapters (PAS, LMS, Commission).

    All adapters transform insurer data into platform Signals,
    regardless of source (batch file, webhook, API).

    Each adapter knows how to:
    - Validate a mapped row
    - Generate an idempotency key to prevent duplicates
    - Process a row into one or more SignalEmit objects
    """

    adapter_type: AdapterType = AdapterType.BATCH_FILE

    @abstractmethod
    async def process_row(
        self, row: dict, tenant_id: uuid.UUID, db: AsyncSession
    ) -> list[SignalEmit]:
        """Process a single mapped row and return signals to emit."""

    @abstractmethod
    def get_idempotency_key(self, row: dict) -> str:
        """Generate a deterministic idempotency key for this row."""

    @abstractmethod
    def validate_row(self, row: dict) -> tuple[bool, list[str]]:
        """Validate a mapped row. Returns (is_valid, list_of_errors)."""
