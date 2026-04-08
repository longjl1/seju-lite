from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class StructuredMemoryFactV2:
    content: str
    category: str = "context"
    confidence: float = 0.7
    source: str = "unknown"


@dataclass(slots=True)
class StructuredMemoryStateV2:
    profile: list[str] = field(default_factory=list)
    current_focus: list[str] = field(default_factory=list)
    recent_history_summary: list[str] = field(default_factory=list)
    background: list[str] = field(default_factory=list)
    facts: list[StructuredMemoryFactV2] = field(default_factory=list)


@dataclass(slots=True)
class StructuredMemoryContextV2:
    text: str
    used_chars: int


@dataclass(slots=True)
class HistoryWindowV2:
    recent_messages: list[dict]
    dropped_messages: list[dict] = field(default_factory=list)
    dropped_count: int = 0


@dataclass(slots=True)
class SummarizationResultV2:
    should_summarize: bool
    kept_messages: list[dict]
    dropped_messages: list[dict]
    summary_prompt: str | None = None
    summary_text: str | None = None
    history_for_model: list[dict] = field(default_factory=list)
