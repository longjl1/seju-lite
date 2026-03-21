from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSpec:
    kind: str
    keywords: tuple[str, ...] = ()
    env_key: str = ""
    display_name: str = ""
    litellm_prefix: str = ""
    skip_prefixes: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        return self.display_name or self.kind


PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        kind="gemini",
        keywords=("gemini",),
        env_key="GEMINI_API_KEY",
        display_name="Gemini",
    ),
    ProviderSpec(
        kind="openai_compatible",
        keywords=("gpt", "openai"),
        display_name="OpenAI Compatible",
    ),
    ProviderSpec(
        kind="deepseek",
        keywords=("deepseek",),
        env_key="DEEPSEEK_API_KEY",
        display_name="DeepSeek",
        litellm_prefix="deepseek",
        skip_prefixes=("deepseek/",),
    ),
    ProviderSpec(
        kind="litellm_deepseek",
        keywords=("deepseek",),
        env_key="DEEPSEEK_API_KEY",
        display_name="LiteLLM DeepSeek",
        litellm_prefix="deepseek",
        skip_prefixes=("deepseek/",),
    ),
)


def find_by_kind(kind: str) -> ProviderSpec | None:
    for spec in PROVIDERS:
        if spec.kind == kind:
            return spec
    return None


def find_by_model(model: str) -> ProviderSpec | None:
    model_lower = model.lower()
    for spec in PROVIDERS:
        if any(keyword in model_lower for keyword in spec.keywords):
            return spec
    return None


def apply_litellm_prefix(model: str, spec: ProviderSpec) -> str:
    if not spec.litellm_prefix:
        return model
    if any(model.startswith(prefix) for prefix in spec.skip_prefixes):
        return model
    return f"{spec.litellm_prefix}/{model}"
