import asyncio
from .events import InboundMessage, OutboundMessage


class MessageBus:
    def __init__(self) -> None:
        self._inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self._outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()

    async def publish_inbound(self, msg: InboundMessage) -> None:
        await self._inbound.put(msg)

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        await self._outbound.put(msg)

    async def consume_inbound(self) -> InboundMessage:
        return await self._inbound.get()

    async def consume_outbound(self) -> OutboundMessage:
        return await self._outbound.get()