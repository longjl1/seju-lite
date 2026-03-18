import httpx
from .base import LLMProvider, LLMResponse, ToolCall


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, base_url: str, api_key: str, model: str, temperature: float = 0.3, max_tokens: int = 1200):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def chat_with_retry(self, messages, tools=None, model=None) -> LLMResponse:
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()

        msg = data["choices"][0]["message"]
        finish_reason = data["choices"][0].get("finish_reason", "stop")

        tool_calls = []
        for tc in msg.get("tool_calls", []) or []:
            tool_calls.append(
                ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=__import__("json").loads(tc["function"]["arguments"])
                )
            )

        return LLMResponse(
            content=msg.get("content"),
            tool_calls=tool_calls,
            finish_reason=finish_reason
        )