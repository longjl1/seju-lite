import json
import os
from typing import Any

from litellm import acompletion

from seju_lite.providers.base import LLMProvider, LLMResponse, ToolCall
from seju_lite.providers.registry import apply_litellm_prefix, find_by_kind


class LiteLLMDeepSeekProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.3,
        max_output_tokens: int = 1200,
        api_base: str | None = None,
        provider_kind: str = "deepseek",
    ):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.api_base = api_base
        self.spec = find_by_kind(provider_kind) or find_by_kind("deepseek")
        if self.spec is None:
            raise ValueError("Provider registry is missing spec for DeepSeek")
        if self.spec.env_key and self.api_key:
            os.environ.setdefault(self.spec.env_key, self.api_key)

    @staticmethod
    def _parse_tool_arguments(raw_args: Any) -> dict[str, Any]:
        if isinstance(raw_args, dict):
            return raw_args
        if isinstance(raw_args, str):
            try:
                parsed = json.loads(raw_args)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}

    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": apply_litellm_prefix(self.model, self.spec),
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": max(1, self.max_output_tokens),
            "api_key": self.api_key,
        }
        if self.api_base:
            payload["api_base"] = self.api_base
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        response = await acompletion(**payload)

        choice = response.choices[0]
        message = choice.message

        tool_calls: list[ToolCall] = []
        for i, tc in enumerate(getattr(message, "tool_calls", []) or []):
            fn = getattr(tc, "function", None)
            name = getattr(fn, "name", None)
            if not name:
                continue
            raw_args = getattr(fn, "arguments", {})
            tool_calls.append(
                ToolCall(
                    id=getattr(tc, "id", None) or f"deepseek_call_{i}",
                    name=name,
                    arguments=self._parse_tool_arguments(raw_args),
                )
            )

        return LLMResponse(
            content=getattr(message, "content", None),
            tool_calls=tool_calls,
            finish_reason=getattr(choice, "finish_reason", None) or "stop",
        )
