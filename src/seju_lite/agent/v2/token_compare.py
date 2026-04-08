from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from seju_lite.agent.context_policy import ContextPolicyDecider
from seju_lite.agent.context_utils import filter_low_signal_history
from seju_lite.agent.v2.runtime_adapter import RuntimeAdapterConfigV2, RuntimeContextAdapterV2
from seju_lite.session.manager import Session


def _normalize_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                parts.append(str(item))
                continue
            item_type = str(item.get("type") or "")
            if item_type == "text":
                parts.append(str(item.get("text") or ""))
            elif item_type == "image_url":
                parts.append("[image]")
            else:
                parts.append(json.dumps(item, ensure_ascii=False, sort_keys=True))
        return "\n".join(part for part in parts if part)
    if content is None:
        return ""
    return json.dumps(content, ensure_ascii=False, sort_keys=True)


def _serialize_messages(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for message in messages:
        role = str(message.get("role") or "unknown")
        content = _normalize_content(message.get("content"))
        if content:
            lines.append(f"{role.upper()}: {content}")
        tool_calls = message.get("tool_calls")
        if tool_calls:
            lines.append(f"TOOL_CALLS: {json.dumps(tool_calls, ensure_ascii=False, sort_keys=True)}")
    return "\n".join(lines)


def estimate_tokens(text: str, model_name: str | None = None) -> tuple[int, str]:
    try:
        import tiktoken  # type: ignore

        encoding = None
        if model_name:
            try:
                encoding = tiktoken.encoding_for_model(model_name)
            except Exception:
                encoding = None
        if encoding is None:
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text)), "tiktoken"
    except Exception:
        estimated = max(1, round(len(text) / 4))
        return estimated, "char_estimate"


@dataclass(slots=True)
class ContextTokenSnapshot:
    mode: str
    message_count: int
    char_count: int
    token_count: int
    tokenizer: str
    history_count: int
    preview: str


async def build_context_token_snapshot(
    *,
    workspace,
    system_prompt: str,
    provider,
    model_name: str,
    session: Session,
    current_message: str,
    channel: str = "cli",
    chat_id: str = "local",
    metadata: dict[str, Any] | None = None,
    max_history: int = 12,
    include_memory: bool = True,
    include_skills: bool = True,
    mode: str = "old",
    summary_trigger_messages: int = 20,
    summary_keep_recent_messages: int = 8,
    summary_max_messages_to_summarize: int = 24,
    respect_policy: bool = True,
) -> ContextTokenSnapshot:
    policy = ContextPolicyDecider(default_history_limit=max_history).decide(current_message)
    if respect_policy:
        raw_history = session.get_history(policy.history_limit) if policy.include_history else []
        effective_include_memory = include_memory and policy.include_memory
        effective_include_skills = include_skills and policy.include_skills
    else:
        raw_history = session.get_history(max_history)
        effective_include_memory = include_memory
        effective_include_skills = include_skills
    history = filter_low_signal_history(raw_history)

    adapter = RuntimeContextAdapterV2(
        workspace=workspace,
        system_prompt=system_prompt,
        config=RuntimeAdapterConfigV2(
            mode=mode,
            include_memory=effective_include_memory,
            llm_summary_trigger_messages=summary_trigger_messages,
            llm_summary_keep_recent_messages=summary_keep_recent_messages,
            llm_summary_max_messages_to_summarize=summary_max_messages_to_summarize,
        ),
    )
    messages = await adapter.build_messages(
        history=history,
        current_message=current_message,
        provider=provider,
        channel=channel,
        chat_id=chat_id,
        metadata=metadata or session.metadata,
        include_memory=effective_include_memory,
        include_skills=effective_include_skills,
    )
    serialized = _serialize_messages(messages)
    token_count, tokenizer = estimate_tokens(serialized, model_name=model_name)
    preview = serialized[:500]
    if len(serialized) > 500:
        preview += "...(truncated)"
    return ContextTokenSnapshot(
        mode=mode,
        message_count=len(messages),
        char_count=len(serialized),
        token_count=token_count,
        tokenizer=tokenizer,
        history_count=len(history),
        preview=preview,
    )
