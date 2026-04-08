from __future__ import annotations

import re
from dataclasses import dataclass, field


_GREETING_RE = re.compile(
    r"^(?:hi|hello|hey|你好|您好|嗨|在吗|早上好|下午好|晚上好)[!！,.，~～\s]*$",
    re.IGNORECASE,
)
_IDENTITY_RE = re.compile(
    r"^(?:你是谁|介绍一下你自己|你能做什么|who are you|what can you do)[?？!！\s]*$",
    re.IGNORECASE,
)
_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*\S)\s*$")
_BULLET_RE = re.compile(r"^\s*[-*+]\s+(.*\S)\s*$")


def filter_low_signal_history(
    history: list[dict[str, object]],
    *,
    keep_last: int = 6,
) -> list[dict[str, object]]:
    """Remove repetitive low-signal turns while preserving recent context."""
    if len(history) <= keep_last:
        return history

    head = history[:-keep_last]
    tail = history[-keep_last:]
    filtered: list[dict[str, object]] = []

    for item in head:
        content = str(item.get("content") or "").strip()
        role = str(item.get("role") or "")
        if not content:
            continue
        if role == "user" and (_GREETING_RE.match(content) or _IDENTITY_RE.match(content)):
            continue
        filtered.append(item)

    return filtered + tail


@dataclass
class StructuredMemory:
    profile: list[str] = field(default_factory=list)
    focus: list[str] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    fallback: list[str] = field(default_factory=list)

    def render(self, max_chars: int = 1600) -> str:
        sections: list[str] = []

        if self.profile:
            sections.append("Profile:\n" + "\n".join(f"- {line}" for line in self.profile[:4]))
        if self.focus:
            sections.append("Current Focus:\n" + "\n".join(f"- {line}" for line in self.focus[:4]))
        if self.facts:
            sections.append("Stable Facts:\n" + "\n".join(f"- {line}" for line in self.facts[:8]))
        if not sections and self.fallback:
            sections.append("Memory Notes:\n" + "\n".join(f"- {line}" for line in self.fallback[:8]))

        content = "\n\n".join(section for section in sections if section.strip())
        if len(content) > max_chars:
            content = content[: max_chars - 4].rstrip() + " ..."
        return content


def parse_memory_markdown(markdown: str) -> StructuredMemory:
    """Extract a compact structured view from MEMORY.md-like markdown."""
    memory = StructuredMemory()
    if not markdown.strip():
        return memory

    sections: dict[str, list[str]] = {}
    current_heading = "general"
    sections[current_heading] = []

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            current_heading = heading_match.group(2).strip()
            sections.setdefault(current_heading, [])
            continue

        bullet_match = _BULLET_RE.match(line)
        if bullet_match:
            sections.setdefault(current_heading, []).append(bullet_match.group(1).strip())
            continue

        if not line.startswith(("```", "---")):
            sections.setdefault(current_heading, []).append(line)

    for heading, items in sections.items():
        if not items:
            continue
        lowered = heading.casefold()
        target = memory.fallback
        if any(token in lowered for token in ("profile", "user", "personal", "context", "偏好", "用户", "背景")):
            target = memory.profile
        elif any(token in lowered for token in ("focus", "current", "active", "todo", "近期", "当前", "进行中")):
            target = memory.focus
        elif any(token in lowered for token in ("fact", "stable", "knowledge", "事实", "知识")):
            target = memory.facts

        for item in items:
            cleaned = item.strip(" -")
            if not cleaned:
                continue
            target.append(cleaned)

    # Promote fallback lines if no dedicated sections were found.
    if not memory.profile and memory.fallback:
        memory.profile.extend(memory.fallback[:3])
    if not memory.facts and len(memory.fallback) > 3:
        memory.facts.extend(memory.fallback[3:8])

    # De-duplicate while preserving order.
    memory.profile = list(dict.fromkeys(memory.profile))
    memory.focus = list(dict.fromkeys(memory.focus))
    memory.facts = list(dict.fromkeys(memory.facts))
    memory.fallback = list(dict.fromkeys(memory.fallback))
    return memory
