from __future__ import annotations

from collections.abc import Callable
from typing import Any

from seju_lite.agent.base import BaseAgent
from seju_lite.agent.loop import AgentLoop
from seju_lite.bus.events import InboundMessage


class LoopAgentAdapter(BaseAgent):
    """Adapter that wraps existing AgentLoop into the BaseAgent interface."""

    def __init__(
        self,
        loop: AgentLoop,
        name: str = "main",
        tool_allowlist_fn: Callable[[], set[str]] | None = None,
    ):
        self._loop = loop
        self.name = name
        self._tool_allowlist_fn = tool_allowlist_fn

    async def run(self, inbound: InboundMessage, context: dict[str, Any] | None = None) -> str:
        _ = context
        allowlist = self._tool_allowlist_fn() if self._tool_allowlist_fn else None
        return await self._loop.process_message(inbound, tool_allowlist=allowlist)


def _all_tool_names(loop: AgentLoop) -> set[str]:
    names: set[str] = set()
    for item in loop.tools.get_definitions():
        name = str(item.get("function", {}).get("name", "")).strip()
        if name:
            names.add(name)
    return names


def _is_network_tool(name: str) -> bool:
    if name == "web_fetch":
        return True
    if name.endswith("_web_fetch"):
        return True
    if name.startswith("mcp_playwright_"):
        return True
    if name.startswith("mcp_notion_"):
        return True
    # external MCP tools by naming convention
    if name.startswith("mcp_") and ("http" in name or "web" in name or "url" in name):
        return True
    return False


def _local_tool_allowlist(loop: AgentLoop) -> set[str]:
    all_names = _all_tool_names(loop)
    return {n for n in all_names if not _is_network_tool(n)}


def _web_tool_allowlist(loop: AgentLoop) -> set[str]:
    all_names = _all_tool_names(loop)
    # web agent focuses on network/external tasks, but can still use time and helper tools.
    keep: set[str] = set()
    for n in all_names:
        if _is_network_tool(n):
            keep.add(n)
        if n in {"time", "mcp_seju_local_time", "spawn", "message_helper"}:
            keep.add(n)
    return keep


def build_default_registry(loop: AgentLoop) -> dict[str, BaseAgent]:
    """Register default agents.

    `rag` and `web` currently reuse the main loop, so routing can be enabled
    now without behavior regressions. Later they can be replaced with specialized
    agent implementations without changing orchestrator wiring.
    """
    main = LoopAgentAdapter(loop=loop, name="main")
    local = LoopAgentAdapter(
        loop=loop,
        name="local",
        tool_allowlist_fn=lambda: _local_tool_allowlist(loop),
    )
    web = LoopAgentAdapter(
        loop=loop,
        name="web",
        tool_allowlist_fn=lambda: _web_tool_allowlist(loop),
    )
    return {
        "main": main,
        "local": local,
        "web": web,
    }
