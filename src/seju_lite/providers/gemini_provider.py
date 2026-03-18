import json
from google import genai
from seju_lite.providers.base import LLMProvider, LLMResponse


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

    def _flatten_messages(self, messages: list[dict]) -> str:
        chunks = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if not content:
                continue
            chunks.append(f"[{role.upper()}]\n{content}")
        return "\n\n".join(chunks)

    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        prompt = self._flatten_messages(messages)

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={
                "temperature": self.temperature,
                "max_output_tokens": self.max_output_tokens,
            },
        )

        text = getattr(response, "text", None)
        return LLMResponse(
            content=text,
            tool_calls=[],
            finish_reason="stop",
        )