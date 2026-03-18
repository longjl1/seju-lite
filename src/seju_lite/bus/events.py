from pydantic import BaseModel, Field
from typing import Any


class InboundMessage(BaseModel):
    channel: str
    sender_id: str
    chat_id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def session_key(self) -> str:
        return f"{self.channel}:{self.chat_id}"


class OutboundMessage(BaseModel):
    channel: str
    chat_id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)