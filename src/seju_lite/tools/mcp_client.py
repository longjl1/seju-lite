"""Simplified MCP client integration for seju-lite.

Flow:
1) Connect to MCP servers
2) List remote tools
3) Wrap each remote tool as a local function tool
4) Register wrapped tools into ToolRegistry
"""

from __future__ import annotations

import asyncio
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Mapping

import httpx
from anyio import ClosedResourceError
from loguru import logger

from seju_lite.tools.registry import ToolRegistry


@dataclass
class MCPServerConfig:
    """Runtime configuration for one MCP server. 
    
    把 config.json 里的 server 配置标准化
    
    """

    type: str | None = None
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    enabled_tools: list[str] = field(default_factory=lambda: ["*"])
    tool_timeout: int = 30

    @classmethod
    def from_raw(cls, raw: Any) -> "MCPServerConfig":
        """Accept dict/object config and normalize field names."""

        if isinstance(raw, cls):
            return raw

        if isinstance(raw, Mapping):
            data = dict(raw)
            return cls(
                type=data.get("type"),
                command=data.get("command"),
                args=list(data.get("args") or []),
                env=dict(data.get("env") or {}),
                url=data.get("url"),
                headers=dict(data.get("headers") or {}),
                enabled_tools=list(
                    data.get("enabled_tools")
                    or data.get("enabledTools")
                    or ["*"]
                ),
                tool_timeout=int(data.get("tool_timeout") or data.get("toolTimeout") or 30),
            )

        # Object-style config (e.g. pydantic model)
        return cls(
            type=getattr(raw, "type", None),
            command=getattr(raw, "command", None),
            args=list(getattr(raw, "args", None) or []),
            env=dict(getattr(raw, "env", None) or {}),
            url=getattr(raw, "url", None),
            headers=dict(getattr(raw, "headers", None) or {}),
            enabled_tools=list(
                getattr(raw, "enabled_tools", None)
                or getattr(raw, "enabledTools", None)
                or ["*"]
            ),
            tool_timeout=int(
                getattr(raw, "tool_timeout", None)
                or getattr(raw, "toolTimeout", None)
                or 30
            ),
        )


class MCPToolWrapper:
    """Wrap one remote MCP tool into seju-lite's local tool interface."""

    def __init__(self, session: Any, server_name: str, tool_def: Any, tool_timeout: int = 30):
        self._session = session
        self._server_name = server_name
        self._original_name = tool_def.name
        self.name = f"mcp_{server_name}_{tool_def.name}"
        self._description = tool_def.description or tool_def.name
        self._parameters = tool_def.inputSchema or {"type": "object", "properties": {}}
        self._tool_timeout = tool_timeout
        self._context: dict[str, Any] = {}

        self.definition = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self._description,
                "parameters": self._parameters,
            },
        }

    def set_context(self, **kwargs: Any) -> None:
        self._context = dict(kwargs)

    async def run(self, **kwargs: Any) -> str:
        if self._server_name == "simple_rag":
            metadata = self._context.get("metadata") or {}
            upload_data_path = metadata.get("upload_data_path")
            rag_index_path = metadata.get("rag_index_path")
            if upload_data_path and "data_path" not in kwargs:
                kwargs = {**kwargs, "data_path": upload_data_path}
            if rag_index_path and "index_path" not in kwargs:
                kwargs = {**kwargs, "index_path": rag_index_path}

        # Notion MCP compatibility: some models emit {"parent":{"type":"workspace"}}
        # while Notion API expects {"parent":{"workspace": true}}.
        if self.name.endswith("API-post-page"):
            parent = kwargs.get("parent")
            if isinstance(parent, dict) and parent.get("type") == "workspace":
                kwargs = {**kwargs, "parent": {"workspace": True}}

        try:
            result = await asyncio.wait_for(
                self._session.call_tool(self._original_name, arguments=kwargs),
                timeout=self._tool_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("MCP tool '{}' timed out after {}s", self.name, self._tool_timeout)
            return f"(MCP tool call timed out after {self._tool_timeout}s)"
        except asyncio.CancelledError:
            task = asyncio.current_task()
            if task is not None and task.cancelling() > 0:
                raise
            logger.warning("MCP tool '{}' was cancelled by server/SDK", self.name)
            return "(MCP tool call was cancelled)"
        except ClosedResourceError:
            logger.error(
                "MCP tool '{}' failed: session stream closed (server process likely exited)",
                self.name,
            )
            return "(MCP tool call failed: session closed; please retry or reconnect MCP server)"
        except Exception as exc:
            logger.exception(
                "MCP tool '{}' failed: {}: {}",
                self.name,
                type(exc).__name__,
                exc,
            )
            return f"(MCP tool call failed: {type(exc).__name__})"

        parts: list[str] = []
        for block in result.content:
            text = getattr(block, "text", None)
            parts.append(text if isinstance(text, str) else str(block))

        return "\n".join(parts) or "(no output)"


async def connect_mcp_servers(
    mcp_servers: Mapping[str, Any],
    registry: ToolRegistry,
    stack: AsyncExitStack,
) -> None:
    """Connect configured MCP servers and register wrapped tools."""

    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.sse import sse_client
        from mcp.client.stdio import stdio_client
        from mcp.client.streamable_http import streamable_http_client
    except Exception as exc:  # pragma: no cover - depends on optional dependency
        logger.error("MCP SDK unavailable: {}", exc)
        return

    for server_name, raw_cfg in mcp_servers.items():
        cfg = MCPServerConfig.from_raw(raw_cfg)

        try:
            transport_type = cfg.type
            if not transport_type:
                if cfg.command:
                    transport_type = "stdio"
                elif cfg.url:
                    transport_type = "sse" if cfg.url.rstrip("/").endswith("/sse") else "streamableHttp"
                else:
                    logger.warning("MCP server '{}': missing command/url, skipped", server_name)
                    continue

            if transport_type == "stdio":
                merged_env = {**os.environ, **cfg.env} if cfg.env else None
                params = StdioServerParameters(
                    command=cfg.command,
                    args=cfg.args,
                    env=merged_env,
                )
                read, write = await stack.enter_async_context(stdio_client(params))

            elif transport_type == "sse":

                def httpx_client_factory(
                    headers: dict[str, str] | None = None,
                    timeout: httpx.Timeout | None = None,
                    auth: httpx.Auth | None = None,
                ) -> httpx.AsyncClient:
                    merged_headers = {**cfg.headers, **(headers or {})}
                    return httpx.AsyncClient(
                        headers=merged_headers or None,
                        follow_redirects=True,
                        timeout=timeout,
                        auth=auth,
                    )

                read, write = await stack.enter_async_context(
                    sse_client(cfg.url, httpx_client_factory=httpx_client_factory)
                )

            elif transport_type == "streamableHttp":
                # Keep HTTP client timeout unbounded here; per-tool timeout still applies.
                http_client = await stack.enter_async_context(
                    httpx.AsyncClient(headers=cfg.headers or None, follow_redirects=True, timeout=None)
                )
                read, write, _ = await stack.enter_async_context(
                    streamable_http_client(cfg.url, http_client=http_client)
                )
            else:
                logger.warning(
                    "MCP server '{}': unknown transport '{}', skipped", server_name, transport_type
                )
                continue

            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            tools_resp = await session.list_tools()
            enabled_tools = set(cfg.enabled_tools)
            allow_all = "*" in enabled_tools

            registered_count = 0
            matched_enabled: set[str] = set()
            raw_names = [tool_def.name for tool_def in tools_resp.tools]
            wrapped_names = [f"mcp_{server_name}_{tool_def.name}" for tool_def in tools_resp.tools]
            registered_wrapped_names: list[str] = []

            if raw_names:
                logger.info(
                    "MCP server '{}': available tools: {}",
                    server_name,
                    ", ".join(raw_names),
                )
            else:
                logger.warning("MCP server '{}': no tools available", server_name)

            for tool_def in tools_resp.tools:
                wrapped_name = f"mcp_{server_name}_{tool_def.name}"

                if (
                    not allow_all
                    and tool_def.name not in enabled_tools
                    and wrapped_name not in enabled_tools
                ):
                    continue

                wrapper = MCPToolWrapper(
                    session=session,
                    server_name=server_name,
                    tool_def=tool_def,
                    tool_timeout=cfg.tool_timeout,
                )

                ''' registry '''
                registry.register(wrapper)
                registered_count += 1
                registered_wrapped_names.append(wrapper.name)

                if tool_def.name in enabled_tools:
                    matched_enabled.add(tool_def.name)
                if wrapped_name in enabled_tools:
                    matched_enabled.add(wrapped_name)

            if enabled_tools and not allow_all:
                unmatched = sorted(enabled_tools - matched_enabled)
                if unmatched:
                    logger.warning(
                        "MCP server '{}': enabled_tools not found: {}. raw: {} wrapped: {}",
                        server_name,
                        ", ".join(unmatched),
                        ", ".join(raw_names) or "(none)",
                        ", ".join(wrapped_names) or "(none)",
                    )

            logger.info(
                "MCP server '{}': connected, {} tools registered",
                server_name,
                registered_count,
            )
            if registered_wrapped_names:
                logger.info(
                    "MCP server '{}': registered wrapped tools: {}",
                    server_name,
                    ", ".join(registered_wrapped_names),
                )
        except Exception as exc:
            logger.error("MCP server '{}': failed to connect: {}", server_name, exc)


class MCPClientHub:
    """Owns MCP connections lifecycle so wrapped tools stay callable."""

    def __init__(self, mcp_servers: Mapping[str, Any]):
        self._mcp_servers = mcp_servers
        self._stack: AsyncExitStack | None = None

    async def start(self, registry: ToolRegistry) -> None:
        if self._stack is not None:
            return

        stack = AsyncExitStack()
        await stack.__aenter__()
        try:
            await connect_mcp_servers(self._mcp_servers, registry, stack)

        except Exception:
            await stack.__aexit__(None, None, None)
            raise
        self._stack = stack

    async def close(self) -> None:
        if self._stack is None:
            return
        stack, self._stack = self._stack, None
        await stack.__aexit__(None, None, None)
