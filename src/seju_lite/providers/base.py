from dataclasses import dataclass
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall]
    finish_reason: str = "stop"

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class LLMProvider:
    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        raise NotImplementedError