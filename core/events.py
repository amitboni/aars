"""
core/events.py — Internal event bus for module-to-module communication.
In-process async bus. Replace with Kafka adapter by changing only this file.
NOT the Signal Stream — signals are domain events in the database.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


@dataclass
class Event:
    event_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tenant_id: UUID | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class SignalReceived(Event):
    signal_id: UUID = field(default_factory=uuid4)
    signal_type: str = ""
    agent_id: UUID | None = None


@dataclass
class LifecycleStateChanged(Event):
    agent_id: UUID = field(default_factory=uuid4)
    previous_state: str = ""
    new_state: str = ""


@dataclass
class PlaybookStepDue(Event):
    execution_id: UUID = field(default_factory=uuid4)
    playbook_id: UUID = field(default_factory=uuid4)
    agent_id: UUID = field(default_factory=uuid4)
    step_number: int = 0


@dataclass
class ADMNudgeRequired(Event):
    adm_id: UUID = field(default_factory=uuid4)
    agent_id: UUID | None = None
    nudge_type: str = ""
    message: str = ""


EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[Event], handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, event: Event) -> None:
        for handler in self._handlers.get(type(event), []):
            try:
                await handler(event)
            except Exception:
                logger.exception(f"Event handler error: {handler.__name__}")


event_bus = EventBus()
