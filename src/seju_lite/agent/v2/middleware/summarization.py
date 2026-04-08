from __future__ import annotations

import re
from dataclasses import dataclass

from seju_lite.agent.v2.types import HistoryWindowV2, SummarizationResultV2

_LOW_SIGNAL_RE = re.compile(
    r"^(?:hi|hello|hey|你好|您好|嗨|在吗|你是谁|what can you do|who are you)[!！?？,.，~～\s]*$",
    re.IGNORECASE,
)

_SUMMARY_PREFIX = "Here is a summary of the conversation to date:"


@dataclass(slots=True)
class SummarizationConfigV2:
    enabled: bool = True
    llm_enabled: bool = False
    trigger_messages: int = 20
    keep_recent_messages: int = 8
    max_messages_to_summarize: int = 24
    preserve_tool_pairs: bool = True


class SummarizationMiddlewareV2:
    """Short-term history processor inspired by DeerFlow's summarization flow.

    Key DeerFlow-style behaviors mirrored here:
    - trigger based on history length
    - preserve the most recent messages
    - avoid splitting assistant/tool exchange bundles
    - optionally replace old history with one synthetic summary message
    """

    def __init__(self, config: SummarizationConfigV2 | None = None):
        self.config = config or SummarizationConfigV2()

    def prepare(self, history: list[dict]) -> SummarizationResultV2:
        cleaned = self._drop_low_signal(history) if self.config.enabled else list(history)
        if not self.config.enabled or len(cleaned) <= self.config.trigger_messages:
            return SummarizationResultV2(
                should_summarize=False,
                kept_messages=cleaned,
                dropped_messages=[],
                summary_prompt=None,
                summary_text=None,
                history_for_model=cleaned,
            )

        split_index = self._compute_split_index(cleaned)
        dropped = cleaned[:split_index]
        kept = cleaned[split_index:]

        if len(dropped) > self.config.max_messages_to_summarize:
            dropped = dropped[-self.config.max_messages_to_summarize :]

        summary_prompt = self._build_summary_prompt(dropped)
        return SummarizationResultV2(
            should_summarize=bool(dropped),
            kept_messages=kept,
            dropped_messages=dropped,
            summary_prompt=summary_prompt if dropped else None,
            summary_text=None,
            history_for_model=kept,
        )

    async def summarize_if_needed(self, history: list[dict], provider) -> SummarizationResultV2:
        prepared = self.prepare(history)
        if (
            not self.config.enabled
            or not self.config.llm_enabled
            or not prepared.should_summarize
            or not prepared.summary_prompt
        ):
            return prepared

        try:
            response = await provider.generate(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You summarize older conversation context for future reuse. "
                            "Return a compact, high-signal summary only."
                        ),
                    },
                    {"role": "user", "content": prepared.summary_prompt},
                ]
            )
            summary_text = str(getattr(response, "content", "") or "").strip()
            if not summary_text:
                return prepared
            summary_message = {
                "role": "user",
                "content": f"{_SUMMARY_PREFIX}\n\n{summary_text}",
            }
            return SummarizationResultV2(
                should_summarize=True,
                kept_messages=prepared.kept_messages,
                dropped_messages=prepared.dropped_messages,
                summary_prompt=prepared.summary_prompt,
                summary_text=summary_text,
                history_for_model=[summary_message, *prepared.kept_messages],
            )
        except Exception:
            return prepared

    def build_window(self, history: list[dict]) -> HistoryWindowV2:
        result = self.prepare(history)
        return HistoryWindowV2(
            recent_messages=result.kept_messages,
            dropped_messages=result.dropped_messages,
            dropped_count=len(result.dropped_messages),
        )

    def _compute_split_index(self, history: list[dict]) -> int:
        keep_count = max(0, self.config.keep_recent_messages)
        split_index = max(0, len(history) - keep_count)
        if not self.config.preserve_tool_pairs:
            return split_index

        while split_index > 0 and split_index < len(history):
            current = history[split_index]
            previous = history[split_index - 1]
            current_role = str(current.get("role") or "")
            previous_role = str(previous.get("role") or "")

            # Do not separate assistant tool-call message from following tool result(s).
            if previous_role == "assistant" and current_role == "tool":
                split_index -= 1
                continue

            # Do not keep a dangling tool result without its initiating assistant message.
            if previous_role == "tool" and current_role == "tool":
                split_index -= 1
                continue

            break
        return split_index

    @staticmethod
    def _drop_low_signal(history: list[dict]) -> list[dict]:
        filtered: list[dict] = []
        for item in history:
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            if str(item.get("role") or "") == "user" and _LOW_SIGNAL_RE.match(content):
                continue
            filtered.append(item)
        return filtered

    @staticmethod
    def _build_summary_prompt(messages: list[dict]) -> str:
        lines = []
        for item in messages:
            role = str(item.get("role") or "unknown").upper()
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            lines.append(f"{role}: {content}")
        transcript = "\n".join(lines)
        return (
            "Summarize the following older conversation context.\n\n"
            "Requirements:\n"
            "- Keep durable goals, constraints, user preferences, and unresolved work\n"
            "- Ignore repetitive greetings, meta chat, and low-value filler\n"
            "- Keep the summary concise and high-signal\n"
            "- Preserve tool-derived conclusions when they matter to future turns\n\n"
            f"{transcript}"
        )
