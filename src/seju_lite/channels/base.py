from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from seju_lite.bus.events import InboundMessage, OutboundMessage


class BaseChannel(ABC):
    name: str = "base"
    display_name: str = "Base"

    def __init__(self, bus, allow_from: list[str] | None = None):
        self.bus = bus
        self.allow_from = set(allow_from or [])
        self._running = False

    def is_allowed(self, sender_id: str) -> bool:
        if not self.allow_from:
            return True
        return str(sender_id) in self.allow_from

    async def publish_inbound(
        self,
        *,
        sender_id: str,
        chat_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self.is_allowed(sender_id):
            return
        inbound = InboundMessage(
            channel=self.name,
            sender_id=str(sender_id),
            chat_id=str(chat_id),
            content=content,
            metadata=metadata or {},
        )
        await self.bus.publish_inbound(inbound)

    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        raise NotImplementedError

    @property
    def is_running(self) -> bool:
        return self._running
