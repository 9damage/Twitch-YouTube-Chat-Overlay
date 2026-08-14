from __future__ import annotations

import asyncio
import logging

from app.core.models import ChatMessage


class EventBus:
    """Bounded FIFO which drops the oldest item during chat floods."""

    def __init__(self, max_size: int = 1000) -> None:
        self.queue: asyncio.Queue[ChatMessage] = asyncio.Queue(maxsize=max_size)
        self._logger = logging.getLogger(__name__)

    def publish_nowait(self, message: ChatMessage) -> None:
        if self.queue.full():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except asyncio.QueueEmpty:
                self._logger.debug("Queue drained while handling overflow")
            self._logger.warning("Chat queue full; dropped oldest message")
        self.queue.put_nowait(message)

    async def publish(self, message: ChatMessage) -> None:
        self.publish_nowait(message)

    async def next(self) -> ChatMessage:
        return await self.queue.get()
