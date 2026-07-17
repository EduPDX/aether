"""In-process event bus: the platform's nervous system.

Modules never call each other to "notify"; they publish topics like
``instance.created`` and interested parties subscribe. A future Redis
adapter can mirror this interface for multi-process deployments.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

log = logging.getLogger(__name__)

Handler = Callable[[str, dict[str, Any]], Awaitable[None] | None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[tuple[str, Handler]] = []

    def subscribe(self, topic_prefix: str, handler: Handler) -> None:
        self._subscribers.append((topic_prefix, handler))

    def unsubscribe(self, handler: Handler) -> None:
        self._subscribers = [(p, h) for p, h in self._subscribers if h is not handler]

    async def publish(self, topic: str, payload: dict[str, Any] | None = None) -> None:
        payload = payload or {}
        for prefix, handler in self._subscribers:
            if not topic.startswith(prefix):
                continue
            try:
                result = handler(topic, payload)
                if asyncio.iscoroutine(result) or isinstance(result, Awaitable):
                    await result
            except Exception:  # noqa: BLE001 — a bad subscriber must not break publishers
                log.exception("event handler failed for topic %s", topic)
