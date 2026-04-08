from __future__ import annotations

from pathlib import Path
from typing import Any

from seju_lite.agent.v2.memory.store import StructuredMemoryStoreV2
from seju_lite.agent.v2.middleware.summarization import SummarizationMiddlewareV2


class ContextAssemblerV2:
    """Standalone context assembler for the experimental v2 pipeline."""

    def __init__(self, workspace: Path, system_prompt: str):
        self.workspace = workspace
        self.system_prompt = system_prompt
        self.memory = StructuredMemoryStoreV2(workspace)
        self.summarization = SummarizationMiddlewareV2()

    def build_messages(
        self,
        *,
        history: list[dict[str, Any]],
        current_message: str,
        channel: str | None = None,
        chat_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        include_memory: bool = True,
    ) -> list[dict[str, Any]]:
        summarized = self.summarization.prepare(history)
        system_parts = [self.system_prompt]

        if include_memory:
            memory_context = self.memory.build_context()
            if memory_context.text:
                system_parts.append(f"# Structured Memory\n\n{memory_context.text}")

        runtime_lines = []
        if channel:
            runtime_lines.append(f"Channel: {channel}")
        if chat_id:
            runtime_lines.append(f"Chat ID: {chat_id}")
        if metadata:
            for key in ("upload_data_path", "rag_index_path"):
                value = metadata.get(key)
                if value:
                    runtime_lines.append(f"{key}: {value}")

        user_content = current_message.strip()
        if runtime_lines:
            user_content = "[Runtime Context]\n" + "\n".join(runtime_lines) + "\n\n" + user_content

        return [
            {"role": "system", "content": "\n\n---\n\n".join(part for part in system_parts if part.strip())},
            *summarized.history_for_model,
            {"role": "user", "content": user_content},
        ]

    async def build_messages_with_optional_summary(
        self,
        *,
        history: list[dict[str, Any]],
        current_message: str,
        provider,
        channel: str | None = None,
        chat_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        include_memory: bool = True,
    ) -> list[dict[str, Any]]:
        summarized = await self.summarization.summarize_if_needed(history, provider)
        system_parts = [self.system_prompt]

        if include_memory:
            memory_context = self.memory.build_context()
            if memory_context.text:
                system_parts.append(f"# Structured Memory\n\n{memory_context.text}")

        runtime_lines = []
        if channel:
            runtime_lines.append(f"Channel: {channel}")
        if chat_id:
            runtime_lines.append(f"Chat ID: {chat_id}")
        if metadata:
            for key in ("upload_data_path", "rag_index_path"):
                value = metadata.get(key)
                if value:
                    runtime_lines.append(f"{key}: {value}")

        user_content = current_message.strip()
        if runtime_lines:
            user_content = "[Runtime Context]\n" + "\n".join(runtime_lines) + "\n\n" + user_content

        return [
            {"role": "system", "content": "\n\n---\n\n".join(part for part in system_parts if part.strip())},
            *summarized.history_for_model,
            {"role": "user", "content": user_content},
        ]
