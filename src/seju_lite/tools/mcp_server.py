"""Expose seju-lite built-in tools as an MCP server."""

from __future__ import annotations

from pathlib import Path

from seju_lite.tools.read_file_tool import ReadFileTool
from seju_lite.tools.time_tool import TimeTool
from seju_lite.tools.web_tool import WebFetchTool


def create_mcp_server(
    *,
    name: str = "seju-lite-tools",
    read_root: Path = Path("./workspace"),
    web_max_chars: int = 12000,
):
    """Build an MCP server that wraps seju-lite local tools."""
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception as exc:  # pragma: no cover - depends on optional dependency
        raise RuntimeError(
            "MCP SDK is not installed. Install it with: pip install mcp"
        ) from exc

    mcp = FastMCP(name=name)
    time_tool = TimeTool()
    read_file_tool = ReadFileTool(read_root)
    web_tool = WebFetchTool(max_chars=web_max_chars)

    @mcp.tool(name=time_tool.name, description=time_tool.definition["function"]["description"])
    async def time() -> str:
        return await time_tool.run()

    @mcp.tool(
        name=read_file_tool.name,
        description=read_file_tool.definition["function"]["description"],
    )
    async def read_file(path: str) -> str:
        return await read_file_tool.run(path=path)

    @mcp.tool(name=web_tool.name, description=web_tool.definition["function"]["description"])
    async def web_fetch(
        url: str,
        extractMode: str = "text",
        maxChars: int | None = None,
    ) -> str:
        return await web_tool.run(url=url, extractMode=extractMode, maxChars=maxChars)

    return mcp


def run_mcp_server(
    *,
    transport: str = "stdio",
    name: str = "seju-lite-tools",
    read_root: Path = Path("./workspace"),
    web_max_chars: int = 12000,
) -> None:
    """Start MCP server process for seju-lite tools."""
    mcp = create_mcp_server(name=name, read_root=read_root, web_max_chars=web_max_chars)
    mcp.run(transport=transport)
