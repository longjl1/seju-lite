from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from seju_lite.agent.context_utils import parse_memory_markdown


_SAVE_MEMORY_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save memory consolidation output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "history_entry": {
                        "type": "string",
                        "description": (
                            "A concise but informative history paragraph. "
                            "Start with [YYYY-MM-DD HH:MM]."
                        ),
                    },
                    "memory_update": {
                        "type": "string",
                        "description": (
                            "Full updated MEMORY.md markdown. Include existing and new stable facts."
                        ),
                    },
                },
                "required": ["history_entry", "memory_update"],
            },
        },
    }
]

# json -> str 
def _ensure_text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


class MemoryStore:
    def __init__(self, workspace: Path):
        self.memory_dir = workspace / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.memory_file = self.memory_dir / "MEMORY.md"
        self.history_file = self.memory_dir / "HISTORY.md"

    def read_long_term(self) -> str:
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return ""

    def write_long_term(self, content: str) -> None:
        self.memory_file.write_text(content, encoding="utf-8")

    def append_history(self, entry: str) -> None: 
        with open(self.history_file, "a", encoding="utf-8") as f: #add to long-term
            f.write(entry.rstrip() + "\n\n")
    # read and get as prompt.. 包装
    def get_memory_context(self) -> str:
        memory = self.read_long_term()
        return f"## Long-term Memory\n{memory}" if memory else ""

    def get_compact_memory_context(self, max_chars: int = 1600) -> str:
        memory = self.read_long_term()
        if not memory:
            return ""
        structured = parse_memory_markdown(memory)
        compact = structured.render(max_chars=max_chars)
        return f"## Long-term Memory\n{compact}" if compact else ""


class MemoryConsolidator:
    """
    · memory consolidation:
    - Archive summarized chunks into HISTORY.md
    - Update MEMORY.md with stable long-term facts
    - Advance session.last_consolidated after successful consolidation
    """

    _MAX_FAILURES_BEFORE_RAW_ARCHIVE = 3

    def __init__(
        self,
        workspace: Path,
        sessions,
        provider,
        max_history: int = 12,
    ):
        self.store = MemoryStore(workspace)
        self.sessions = sessions
        self.provider = provider
        self.max_unconsolidated = max(max_history * 2, 24) # 未归档上限
        self.keep_recent = max(max_history, 8) # 至少保留不归档消息数
        self._consecutive_failures = 0

    @staticmethod
    def _format_messages(messages: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for msg in messages:
            content = msg.get("content")
            if not content:
                continue
            role = str(msg.get("role", "unknown")).upper()
            ts = str(msg.get("timestamp", "?"))[:16] # 截取时间调整
            lines.append(f"[{ts}] {role}: {content}")
        return "\n".join(lines)
    # 归档 msg chunck -> update long-term mmr
    async def consolidate_messages(self, messages: list[dict[str, Any]]) -> bool:
        if not messages:
            return True

        current_memory = self.store.read_long_term()
        prompt = (
            "Process this conversation and call save_memory.\n\n"
            "## Current Long-term Memory\n"
            f"{current_memory or '(empty)'}\n\n"
            "## Conversation to Process\n"
            f"{self._format_messages(messages)}"
        )

        chat_messages = [
            {
                "role": "system",
                "content": (
                    "You are a memory consolidation agent. "
                    "Always call the save_memory tool."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.provider.generate(
                messages=chat_messages,
                tools=_SAVE_MEMORY_TOOL,
            )

            if not response.has_tool_calls:
                return self._fail_or_raw_archive(messages)

            save_call = next((tc for tc in response.tool_calls if tc.name == "save_memory"), None)
            if save_call is None or not isinstance(save_call.arguments, dict):
                return self._fail_or_raw_archive(messages)

            if "history_entry" not in save_call.arguments or "memory_update" not in save_call.arguments:
                return self._fail_or_raw_archive(messages)

            entry = _ensure_text(save_call.arguments["history_entry"]).strip()
            update = _ensure_text(save_call.arguments["memory_update"])
            if not entry:
                return self._fail_or_raw_archive(messages)

            self.store.append_history(entry)
            if update != current_memory:
                self.store.write_long_term(update)

            self._consecutive_failures = 0
            return True
        except Exception:
            return self._fail_or_raw_archive(messages)

    def _fail_or_raw_archive(self, messages: list[dict[str, Any]]) -> bool:
        self._consecutive_failures += 1
        if self._consecutive_failures < self._MAX_FAILURES_BEFORE_RAW_ARCHIVE:
            return False
        self._raw_archive(messages)
        self._consecutive_failures = 0
        return True

    def _raw_archive(self, messages: list[dict[str, Any]]) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        payload = self._format_messages(messages)
        self.store.append_history(f"[{ts}] [RAW] {len(messages)} messages\n{payload}")

    # archive
    async def archive_messages(self, messages: list[dict[str, Any]]) -> bool:
        if not messages:
            return True
        for _ in range(self._MAX_FAILURES_BEFORE_RAW_ARCHIVE): # edit here
            if await self.consolidate_messages(messages):
                return True
        return True

    def _pick_boundary(self, session) -> int | None:
        start = session.last_consolidated
        target_end = len(session.messages) - self.keep_recent
        if target_end <= start: return None

        boundary = None
        for idx in range(start + 1, target_end + 1): 
            if session.messages[idx].get("role") == "user": 
                boundary = idx
        return boundary or target_end # None?

    async def auto_consolidate(self, session) -> None:
        num_messages = len(session.messages)
        start = session.last_consolidated
        # if do not reach the upper bound
        if num_messages - start <= self.max_unconsolidated: return

        while num_messages - start > self.max_unconsolidated:
            end = self._pick_boundary(session)

            if end is None or end <= start: return   
            chunk = session.messages[start:end]
            if not chunk: return
            if not await self.consolidate_messages(chunk): return
            
            start = end
            session.last_consolidated = start
            self.sessions.save(session)
