"""modules/channel/voice/dnd_checker.py — DND/NCPR registry check stub.

Before EVERY voice call, check if the phone number is on the DND registry.
Our calls are "service" calls (existing agent-insurer relationship) and are
classified as transactional, not promotional. Transactional calls are allowed
even to DND numbers — but this must be confirmed per tenant's legal team.

Cache DND check results for 30 days.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

DND_CACHE_DAYS = 30


@dataclass
class DNDCheckResult:
    phone: str
    is_registered: bool
    checked_at: datetime
    call_type: str = "transactional"  # transactional or promotional

    @property
    def is_stale(self) -> bool:
        cutoff = datetime.now(timezone.utc) - timedelta(days=DND_CACHE_DAYS)
        return self.checked_at < cutoff

    @property
    def can_call(self) -> bool:
        """Transactional calls are allowed even for DND numbers."""
        return self.call_type == "transactional" or not self.is_registered


class BaseDNDChecker(ABC):
    @abstractmethod
    async def check(self, phone: str) -> DNDCheckResult:
        """Check if a phone number is on the DND registry."""
        ...

    @abstractmethod
    async def batch_check(self, phones: list[str]) -> list[DNDCheckResult]:
        """Batch check multiple numbers."""
        ...


class MockDNDChecker(BaseDNDChecker):
    """Mock DND checker for development and testing.

    Returns not-registered by default. Use set_registered() to configure
    specific numbers as DND-registered for testing.
    """

    def __init__(self) -> None:
        self._registered: set[str] = set()

    def set_registered(self, *phones: str) -> None:
        """Mark phone numbers as DND-registered."""
        self._registered.update(phones)

    def clear(self) -> None:
        self._registered.clear()

    async def check(self, phone: str) -> DNDCheckResult:
        return DNDCheckResult(
            phone=phone,
            is_registered=phone in self._registered,
            checked_at=datetime.now(timezone.utc),
            call_type="transactional",
        )

    async def batch_check(self, phones: list[str]) -> list[DNDCheckResult]:
        return [await self.check(phone) for phone in phones]
