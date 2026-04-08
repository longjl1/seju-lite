from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from seju_lite.agent.v2.types import (
    StructuredMemoryContextV2,
    StructuredMemoryFactV2,
    StructuredMemoryStateV2,
)


class StructuredMemoryStoreV2:
    """Side-by-side structured memory store for the v2 design."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_dir = workspace / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.memory_dir / "memory.v2.json"

    def load(self) -> StructuredMemoryStateV2:
        if not self.state_file.exists():
            return StructuredMemoryStateV2()
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
        except Exception:
            return StructuredMemoryStateV2()
        return self._deserialize(payload)

    def save(self, state: StructuredMemoryStateV2) -> None:
        payload = {
            "profile": state.profile,
            "current_focus": state.current_focus,
            "recent_history_summary": state.recent_history_summary,
            "background": state.background,
            "facts": [
                {
                    "content": fact.content,
                    "category": fact.category,
                    "confidence": fact.confidence,
                    "source": fact.source,
                }
                for fact in state.facts
            ],
        }
        self.state_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def build_context(self, max_chars: int = 1600) -> StructuredMemoryContextV2:
        state = self.load()
        sections: list[str] = []

        if state.profile:
            sections.append("Profile:\n" + "\n".join(f"- {item}" for item in state.profile[:4]))
        if state.current_focus:
            sections.append(
                "Current Focus:\n" + "\n".join(f"- {item}" for item in state.current_focus[:4])
            )
        if state.recent_history_summary:
            sections.append(
                "Recent Summary:\n"
                + "\n".join(f"- {item}" for item in state.recent_history_summary[:4])
            )
        if state.background:
            sections.append(
                "Background:\n" + "\n".join(f"- {item}" for item in state.background[:3])
            )
        if state.facts:
            ranked = sorted(state.facts, key=lambda fact: fact.confidence, reverse=True)
            fact_lines = [
                f"- [{fact.category} | {fact.confidence:.2f}] {fact.content}"
                for fact in ranked[:8]
                if fact.content.strip()
            ]
            if fact_lines:
                sections.append("Stable Facts:\n" + "\n".join(fact_lines))

        text = "\n\n".join(sections).strip()
        if len(text) > max_chars:
            text = text[: max_chars - 4].rstrip() + " ..."
        return StructuredMemoryContextV2(text=text, used_chars=len(text))

    def merge_update(
        self,
        *,
        profile: list[str] | None = None,
        current_focus: list[str] | None = None,
        recent_history_summary: list[str] | None = None,
        background: list[str] | None = None,
        facts: list[StructuredMemoryFactV2] | None = None,
    ) -> StructuredMemoryStateV2:
        state = self.load()
        if profile is not None:
            state.profile = _dedupe(profile)
        if current_focus is not None:
            state.current_focus = _dedupe(current_focus)
        if recent_history_summary is not None:
            state.recent_history_summary = _dedupe(recent_history_summary)
        if background is not None:
            state.background = _dedupe(background)
        if facts is not None:
            merged = list(state.facts)
            existing_keys = {fact.content.casefold(): idx for idx, fact in enumerate(merged)}
            for fact in facts:
                key = fact.content.casefold()
                if key in existing_keys:
                    merged[existing_keys[key]] = fact
                else:
                    merged.append(fact)
            state.facts = merged
        self.save(state)
        return state

    @staticmethod
    def _deserialize(payload: dict[str, Any]) -> StructuredMemoryStateV2:
        facts = []
        for item in payload.get("facts", []):
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            facts.append(
                StructuredMemoryFactV2(
                    content=content,
                    category=str(item.get("category") or "context"),
                    confidence=float(item.get("confidence") or 0.7),
                    source=str(item.get("source") or "unknown"),
                )
            )
        return StructuredMemoryStateV2(
            profile=_dedupe(_coerce_lines(payload.get("profile"))),
            current_focus=_dedupe(_coerce_lines(payload.get("current_focus"))),
            recent_history_summary=_dedupe(_coerce_lines(payload.get("recent_history_summary"))),
            background=_dedupe(_coerce_lines(payload.get("background"))),
            facts=facts,
        )


def _coerce_lines(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _dedupe(lines: list[str]) -> list[str]:
    return list(dict.fromkeys(line.strip() for line in lines if line.strip()))
