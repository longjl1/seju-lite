from __future__ import annotations

from typing import Any

import httpx

from seju_lite.bus.events import OutboundMessage
from seju_lite.channels.base import BaseChannel


class WhatsAppChannel(BaseChannel):
    """
    WhatsApp Cloud API channel (minimal framework).

    Current scope:
    - outbound send is implemented
    - inbound webhook handling can call `handle_webhook_payload(...)`
    """

    name = "whatsapp"
    display_name = "WhatsApp"

    def __init__(
        self,
        token: str,
        phone_number_id: str,
        bus,
        allow_from: list[str] | None = None,
        api_base: str = "https://graph.facebook.com/v22.0",
    ):
        super().__init__(bus=bus, allow_from=allow_from)
        self.token = token
        self.phone_number_id = phone_number_id
        self.api_base = api_base.rstrip("/")

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        url = f"{self.api_base}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": msg.chat_id,
            "type": "text",
            "text": {"body": msg.content},
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()

    async def handle_webhook_payload(self, payload: dict[str, Any]) -> None:
        """
        Parse WhatsApp webhook payload and publish inbound messages.
        This is intentionally lightweight and can be expanded later.
        """
        for entry in payload.get("entry", []) or []:
            for change in entry.get("changes", []) or []:
                value = change.get("value", {}) or {}
                for message in value.get("messages", []) or []:
                    if message.get("type") != "text":
                        continue
                    sender_id = message.get("from")
                    text_obj = message.get("text", {}) or {}
                    text = text_obj.get("body", "")
                    if not sender_id or not text:
                        continue
                    await self.publish_inbound(
                        sender_id=str(sender_id),
                        chat_id=str(sender_id),
                        content=text,
                        metadata={"message_id": message.get("id", "")},
                    )
