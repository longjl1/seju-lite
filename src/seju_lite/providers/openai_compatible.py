import asyncio
import json
from typing import Any

import httpx

from .base import LLMProvider, LLMResponse, ToolCall


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, base_url: str, api_key: str, model: str, temperature: float = 0.3, max_tokens: int = 1200):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        client_kwargs = {
            "timeout": httpx.Timeout(60, connect=10),
            "limits": httpx.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=30),
            "http2": True,
        }
        try:
            self._client = httpx.AsyncClient(**client_kwargs)
        except ImportError:
            # Optional dependency h2 is missing, fallback to HTTP/1.1.
            client_kwargs["http2"] = False
            self._client = httpx.AsyncClient(**client_kwargs)

    @staticmethod
    def _is_retryable_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        retry_markers = [
            "429",
            "503",
            "resource_exhausted",
            "unavailable",
            "timeout",
            "connection",
        ]
        return any(marker in msg for marker in retry_markers)

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

    async def _generate_impl(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model_override: str | None = None,
    ) -> LLMResponse:
        payload = {
            "model": model_override or self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        data: dict[str, Any] | None = None
        attempts = 3
        base_delay = 1.0
        for i in range(attempts):
            try:
                resp = await self._client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as exc:
                is_last = i == attempts - 1
                if not self._is_retryable_error(exc) or is_last:
                    raise
                await asyncio.sleep(base_delay * (2**i))

        if data is None:
            raise RuntimeError("OpenAI-compatible provider returned no response")

        msg = data["choices"][0]["message"]
        finish_reason = data["choices"][0].get("finish_reason", "stop")

        tool_calls: list[ToolCall] = []
        for tc in msg.get("tool_calls", []) or []:
            fn = tc.get("function") or {}
            name = fn.get("name")
            if not name:
                continue
            tool_calls.append(
                ToolCall(
                    id=tc.get("id") or f"openai_compatible_call_{len(tool_calls)}",
                    name=name,
                    arguments=self._parse_tool_arguments(fn.get("arguments", {})),
                )
            )

        return LLMResponse(
            content=msg.get("content"),
            tool_calls=tool_calls,
            finish_reason=finish_reason,
        )

    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        return await self._generate_impl(messages=messages, tools=tools)

    async def chat_with_retry(self, messages, tools=None, model=None) -> LLMResponse:
        # Backward-compatible alias for older call sites.
        return await self._generate_impl(messages=messages, tools=tools, model_override=model)

    async def close(self) -> None:
        await self._client.aclose()
