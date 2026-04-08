from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextPolicy:
    mode: str = "default"
    include_history: bool = True
    include_memory: bool = True
    include_skills: bool = True
    history_limit: int = 8


class ContextPolicyDecider:
    _GREETING_MESSAGES = {
        "hi",
        "hello",
        "hey",
        "你好",
        "您好",
        "嗨",
        "在吗",
    }

    _CREATIVE_HINTS = (
        "讲个故事",
        "写个故事",
        "故事",
        "写首诗",
        "写诗",
        "脑洞",
        "虚构一个",
        "编一个",
    )

    _CONTEXTUAL_CREATIVE_HINTS = (
        "基于之前",
        "根据之前",
        "延续刚才",
        "按之前设定",
        "继续刚才",
        "用之前的设定",
    )

    def __init__(self, default_history_limit: int = 8) -> None:
        self.default_history_limit = max(0, int(default_history_limit))

    def decide(self, message: str) -> ContextPolicy:
        text = (message or "").strip()
        lowered = text.lower()

        if lowered in self._GREETING_MESSAGES:
            return ContextPolicy(
                mode="minimal",
                include_history=False,
                include_memory=False,
                include_skills=False,
                history_limit=0,
            )

        if any(hint in text for hint in self._CREATIVE_HINTS):
            if any(hint in text for hint in self._CONTEXTUAL_CREATIVE_HINTS):
                return ContextPolicy(
                    mode="creative_contextual",
                    include_history=True,
                    include_memory=True,
                    include_skills=False,
                    history_limit=min(self.default_history_limit, 4),
                )
            return ContextPolicy(
                mode="creative_clean",
                include_history=False,
                include_memory=False,
                include_skills=False,
                history_limit=0,
            )

        return ContextPolicy(history_limit=self.default_history_limit)
