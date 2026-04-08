from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from seju_lite.agent.context import ContextBuilder
from seju_lite.agent.v2.context.assembler import ContextAssemblerV2
from seju_lite.agent.v2.middleware.summarization import (
    SummarizationConfigV2,
    SummarizationMiddlewareV2,
)

RuntimeModeV2 = Literal["old", "v2_trim", "v2_llm_summary"]


@dataclass(slots=True)
class RuntimeAdapterConfigV2:
    mode: RuntimeModeV2 = "old"
    include_memory: bool = True
    llm_summary_trigger_messages: int = 20
    llm_summary_keep_recent_messages: int = 8
    llm_summary_max_messages_to_summarize: int = 24


class RuntimeContextAdapterV2:
    """Bridges the existing runtime shape to the isolated v2 context pipeline.

    This adapter is intentionally additive: callers can keep using the original
    `ContextBuilder` path, or switch to one of the v2 modes without changing the
    rest of the loop contract.
    """

    def __init__(self, workspace: Path, system_prompt: str, config: RuntimeAdapterConfigV2 | None = None):
        self.workspace = workspace
        self.config = config or RuntimeAdapterConfigV2()
        self.legacy = ContextBuilder(workspace=workspace, system_prompt=system_prompt)
        self.v2 = ContextAssemblerV2(workspace=workspace, system_prompt=system_prompt)
        self.v2.summarization = SummarizationMiddlewareV2(
            SummarizationConfigV2(
                enabled=self.config.mode != "old",
                llm_enabled=self.config.mode == "v2_llm_summary",
                trigger_messages=self.config.llm_summary_trigger_messages,
                keep_recent_messages=self.config.llm_summary_keep_recent_messages,
                max_messages_to_summarize=self.config.llm_summary_max_messages_to_summarize,
            )
        )

    async def build_messages(
        self,
        *,
        history: list[dict[str, Any]],
        current_message: str,
        provider=None,
        channel: str | None = None,
        chat_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        skill_names: list[str] | None = None,
        media: list[str] | None = None,
        current_role: str = "user",
        include_memory: bool | None = None,
        include_skills: bool = True,
    ) -> list[dict[str, Any]]:
        """Build runtime messages using legacy or v2 strategy."""
        include_memory = self.config.include_memory if include_memory is None else include_memory

        if self.config.mode == "old":
            return self.legacy.build_messages(
                history=history,
                current_message=current_message,
                channel=channel,
                chat_id=chat_id,
                metadata=metadata,
                skill_names=skill_names,
                media=media,
                current_role=current_role,
                include_memory=include_memory,
                include_skills=include_skills,
            )

        if self.config.mode == "v2_llm_summary" and provider is not None:
            return await self.v2.build_messages_with_optional_summary(
                history=history,
                current_message=current_message,
                provider=provider,
                channel=channel,
                chat_id=chat_id,
                metadata=metadata,
                include_memory=include_memory,
            )

        return self.v2.build_messages(
            history=history,
            current_message=current_message,
            channel=channel,
            chat_id=chat_id,
            metadata=metadata,
            include_memory=include_memory,
        )
