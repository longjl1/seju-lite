from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from seju_lite.bus.events import InboundMessage


class BaseAgent(ABC):
    """Common interface for all agents used by orchestrator."""

    name: str = "base"

    @abstractmethod
    async def run(self, inbound: InboundMessage, context: dict[str, Any] | None = None) -> str:
        raise NotImplementedError
