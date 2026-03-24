from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

from seju_lite.agent.loop import AgentLoop
from seju_lite.agent.orchestrator import AgentOrchestrator
from seju_lite.agent.registry import build_default_registry
from seju_lite.agent.workflow_orchestrator import WorkflowOrchestrator
from seju_lite.bus.queue import MessageBus
from seju_lite.channels.registry import discover_all as discover_channels
from seju_lite.config.loader import load_config
from seju_lite.config.schema import RootConfig
from seju_lite.providers.base import LLMProvider
from seju_lite.providers.gemini_provider import GeminiProvider
from seju_lite.providers.litellm_deepseek_provider import LiteLLMDeepSeekProvider
from seju_lite.providers.openai_compatible import OpenAICompatibleProvider
from seju_lite.providers.registry import find_by_kind
from seju_lite.tools.mcp_client import MCPClientHub


@dataclass
class SejuApp:
    config: RootConfig
    bus: MessageBus
    provider: LLMProvider
    agent: AgentLoop
    orchestrator: AgentOrchestrator
    workflow_orchestrator: WorkflowOrchestrator
    channels: dict[str, Any]
    mcp_client_hub: MCPClientHub | None = None


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def _build_gemini(config: RootConfig) -> LLMProvider:
    return GeminiProvider(
        api_key=config.provider.apiKey,
        model=config.provider.model,
        temperature=config.provider.temperature,
        max_output_tokens=config.provider.maxOutputTokens,
    )


def _build_openai_compatible(config: RootConfig) -> LLMProvider:
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


def _build_litellm_deepseek(config: RootConfig) -> LLMProvider:
    return LiteLLMDeepSeekProvider(
        api_key=config.provider.apiKey,
        model=config.provider.model,
        temperature=config.provider.temperature,
        max_output_tokens=config.provider.maxOutputTokens,
        api_base=config.provider.apiBase,
        provider_kind=config.provider.kind,
    )


PROVIDER_BUILDERS: dict[str, Callable[[RootConfig], LLMProvider]] = {
    "gemini": _build_gemini,
    "openai_compatible": _build_openai_compatible,
    "deepseek": _build_litellm_deepseek,
    "litellm_deepseek": _build_litellm_deepseek,
}


def build_provider(config: RootConfig) -> LLMProvider:
    kind = config.provider.kind
    if find_by_kind(kind) is None:
        raise ValueError(f"Unsupported provider kind: {kind}")

    builder = PROVIDER_BUILDERS.get(kind)
    if builder is None:
        raise ValueError(f"Provider kind '{kind}' is not wired in PROVIDER_BUILDERS")
    return builder(config)


async def create_app(config_path: str | Path) -> SejuApp:
    config_path = Path(config_path)
    load_dotenv(config_path.with_name(".env"), override=False)
    load_dotenv(override=False)

    config = load_config(config_path)
    setup_logging(config.app.logLevel)

    bus = MessageBus()
    provider = build_provider(config)
    agent = AgentLoop(config=config, provider=provider, bus=bus)
    agent_registry = build_default_registry(agent)
    orchestrator = AgentOrchestrator(
        agents=agent_registry,
        mode=config.agent.mode,
        default_agent=config.agent.defaultAgent,
        routing=config.agent.routing,
    )
    workflow_orchestrator = WorkflowOrchestrator(
        orchestrator,
        provider=provider,
        enable_llm_planner=config.agent.enableLlmPlanner,
        planner_confidence_threshold=config.agent.plannerConfidenceThreshold,
    )
    mcp_client_hub: MCPClientHub | None = None

    """ start mcp client @ start """
    if config.tools.mcp.enabled and config.tools.mcp.servers:
        mcp_client_hub = MCPClientHub(config.tools.mcp.servers)
        await mcp_client_hub.start(agent.tools)

    channel_instances: dict[str, Any] = {}
    discovered = discover_channels()

    if config.channels.telegram.enabled:
        channel_cls = discovered.get("telegram")
        if channel_cls is None:
            raise RuntimeError("Telegram channel is enabled but no 'telegram' channel class is registered")
        channel_instances["telegram"] = channel_cls(
            token=config.channels.telegram.token,
            bus=bus,
            allow_from=config.channels.telegram.allowFrom,
        )

    if config.channels.whatsapp.enabled:
        channel_cls = discovered.get("whatsapp")
        if channel_cls is None:
            raise RuntimeError("WhatsApp channel is enabled but no 'whatsapp' channel class is registered")
        if not config.channels.whatsapp.token:
            raise ValueError("channels.whatsapp.token is required when WhatsApp is enabled")
        if not config.channels.whatsapp.phoneNumberId:
            raise ValueError("channels.whatsapp.phoneNumberId is required when WhatsApp is enabled")
        channel_instances["whatsapp"] = channel_cls(
            token=config.channels.whatsapp.token,
            phone_number_id=config.channels.whatsapp.phoneNumberId,
            api_base=config.channels.whatsapp.apiBase,
            bus=bus,
            allow_from=config.channels.whatsapp.allowFrom,
        )

    if config.channels.discord.enabled:
        channel_cls = discovered.get("discord")
        if channel_cls is None:
            raise RuntimeError("Discord channel is enabled but no 'discord' channel class is registered")
        if not config.channels.discord.token:
            raise ValueError("channels.discord.token is required when Discord is enabled")
        channel_instances["discord"] = channel_cls(
            token=config.channels.discord.token,
            bus=bus,
            allow_from=config.channels.discord.allowFrom,
            group_policy=config.channels.discord.groupPolicy,
        )

    return SejuApp(
        config=config,
        bus=bus,
        provider=provider,
        agent=agent,
        orchestrator=orchestrator,
        workflow_orchestrator=workflow_orchestrator,
        channels=channel_instances,
        mcp_client_hub=mcp_client_hub,
    )
