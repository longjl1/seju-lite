from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging
import os

from dotenv import load_dotenv

from seju_lite.agent.loop import AgentLoop
from seju_lite.bus.queue import MessageBus
from seju_lite.channels.telegram_bot import TelegramChannel
from seju_lite.config.loader import load_config
from seju_lite.config.schema import RootConfig
from seju_lite.providers.base import LLMProvider
from seju_lite.providers.gemini_provider import GeminiProvider
from seju_lite.providers.openai_compatible import OpenAICompatibleProvider


@dataclass
class SejuApp:
    config: RootConfig
    bus: MessageBus
    provider: LLMProvider
    agent: AgentLoop
    telegram: TelegramChannel | None = None


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def build_provider(config: RootConfig) -> LLMProvider:
    kind = config.provider.kind

    if kind == "gemini":
        return GeminiProvider(
            api_key=config.provider.apiKey,
            model=config.provider.model,
            temperature=config.provider.temperature,
            max_output_tokens=config.provider.maxOutputTokens,
        )

    # 这里给 openai_compatible 留好扩展位
    # 你需要把 schema.py 的 ProviderConfig.kind 改成:
    # Literal["gemini", "openai_compatible"]
    if kind == "openai_compatible":
        base_url = os.getenv("OPENAI_COMPATIBLE_BASE_URL", "").strip()
        if not base_url:
            raise ValueError("OPENAI_COMPATIBLE_BASE_URL is not set")

        return OpenAICompatibleProvider(
            base_url=base_url,
            api_key=config.provider.apiKey,
            model=config.provider.model,
            temperature=config.provider.temperature,
            max_tokens=config.provider.maxOutputTokens,
        )

    raise ValueError(f"Unsupported provider kind: {kind}")


async def create_app(config_path: str | Path) -> SejuApp:
    config_path = Path(config_path)
    # Load env vars before parsing config placeholders like ${GEMINI_API_KEY}.
    # Prefer .env near the config file, then fall back to default lookup.
    load_dotenv(config_path.with_name(".env"), override=False)
    load_dotenv(override=False)

    config = load_config(config_path)
    setup_logging(config.app.logLevel)

    bus = MessageBus()
    provider = build_provider(config)
    agent = AgentLoop(config=config, provider=provider, bus=bus)

    telegram = None
    if config.channels.telegram.enabled:
        telegram = TelegramChannel(
            token=config.channels.telegram.token,
            bus=bus,
            allow_from=config.channels.telegram.allowFrom,
        )

    return SejuApp(
        config=config,
        bus=bus,
        provider=provider,
        agent=agent,
        telegram=telegram,
    )
