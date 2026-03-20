import asyncio
import json
from typing import Any

from google import genai
from google.genai import types

from seju_lite.providers.base import LLMProvider, LLMResponse, ToolCall


class GeminiProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.3,
        max_output_tokens: int = 1200,
    ):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    @staticmethod
    def _is_retryable_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        retry_markers = [
            "503",
            "unavailable",
            "high demand",
            "temporarily unavailable",
            "429",
            "resource_exhausted",
            "deadline exceeded",
            "timeout",
            "connection",
        ]
        return any(marker in msg for marker in retry_markers)


    def _build_gemini_tools(self, tools: list[dict] | None) -> list[types.Tool] | None:
        if not tools:
            return None

        declarations: list[types.FunctionDeclaration] = []
        for tool in tools:
            fn = tool.get("function") or {}
            name = fn.get("name")
            if not name:
                continue

            parameters = fn.get("parameters") or {"type": "object", "properties": {}}
            declarations.append(
                types.FunctionDeclaration(
                    name=name,
                    description=fn.get("description"),
                    parametersJsonSchema=parameters,
                )
            )

        if not declarations:
            return None
        return [types.Tool(functionDeclarations=declarations)]

    def _parse_tool_args(self, raw_args: Any) -> dict[str, Any]:
        if isinstance(raw_args, dict):
            return raw_args
        if isinstance(raw_args, str):
            try:
                parsed = json.loads(raw_args)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}

    def _extract_text_from_content(self, content: Any) -> str | None:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text":
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        chunks.append(text)
            if chunks:
                return "\n".join(chunks)
        return None

    def _build_contents(self, messages: list[dict]) -> tuple[str | None, list[types.Content]]:
        system_parts: list[str] = []
        contents: list[types.Content] = []

        for m in messages:
            role = m.get("role", "user")

            if role == "system":
                text = m.get("content")
                if text:
                    system_parts.append(str(text))
                continue

            if role == "assistant":
                parts: list[types.Part] = []
                text = m.get("content")
                if text:
                    parts.append(types.Part.from_text(text=str(text)))

                for tc in m.get("tool_calls") or []:
                    fn = tc.get("function") or {}
                    name = fn.get("name")
                    if not name:
                        continue
                    args = self._parse_tool_args(fn.get("arguments"))
                    parts.append(types.Part.from_function_call(name=name, args=args))

                if parts:
                    contents.append(types.Content(role="model", parts=parts))
                continue

            if role == "tool":
                name = m.get("name")
                if name:
                    result = m.get("content")
                    contents.append(
                        types.Content(
                            role="tool",
                            parts=[
                                types.Part.from_function_response(
                                    name=str(name),
                                    response={"result": "" if result is None else str(result)},
                                )
                            ],
                        )
                    )
                continue

            # default user-like message
            text = self._extract_text_from_content(m.get("content"))
            if text:
                contents.append(
                    types.Content(role="user", parts=[types.Part.from_text(text=str(text))])
                )

        system_instruction = "\n\n".join(system_parts) if system_parts else None
        return system_instruction, contents

    def _safe_text(self, response: types.GenerateContentResponse) -> str | None:
        try:
            text = response.text
            if text:
                return text
        except Exception:
            pass

        candidates = getattr(response, "candidates", None) or []
        for cand in candidates:
            content = getattr(cand, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                part_text = getattr(part, "text", None)
                if part_text:
                    return str(part_text)
        return None

    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        system_instruction, contents = self._build_contents(messages)
        gemini_tools = self._build_gemini_tools(tools)

        config = types.GenerateContentConfig(
            systemInstruction=system_instruction,
            temperature=self.temperature,
            maxOutputTokens=self.max_output_tokens,
            tools=gemini_tools,
        )

        response = None
        attempts = 3
        base_delay = 1.0
        for i in range(attempts):
            try:
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.model,
                    contents=contents or [types.Content(role="user", parts=[types.Part.from_text(text="")])],
                    config=config,
                )
                break
            except Exception as exc:
                is_last = i == attempts - 1
                if not self._is_retryable_error(exc) or is_last:
                    raise
                await asyncio.sleep(base_delay * (2 ** i))

        if response is None:
            raise RuntimeError("Gemini returned no response")

        text = self._safe_text(response)
        raw_function_calls = getattr(response, "function_calls", None) or []
        tool_calls: list[ToolCall] = []
        for i, fc in enumerate(raw_function_calls):
            name = getattr(fc, "name", None)
            if not name:
                continue
            args = self._parse_tool_args(getattr(fc, "args", {}))
            call_id = getattr(fc, "id", None) or f"gemini_call_{i}"
            tool_calls.append(ToolCall(id=str(call_id), name=str(name), arguments=args))

        finish_reason = "stop"
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            candidate_reason = getattr(candidates[0], "finish_reason", None)
            if candidate_reason is not None:
                finish_reason = str(candidate_reason)

        return LLMResponse(
            content=text,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
        )
