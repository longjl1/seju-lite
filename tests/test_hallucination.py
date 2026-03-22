from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from anyio import ClosedResourceError

from seju_lite.agent.loop import AgentLoop
from seju_lite.bus.events import InboundMessage
from seju_lite.providers.base import LLMResponse, ToolCall
from seju_lite.tools.mcp_client import MCPToolWrapper
from seju_lite.tools.read_file_tool import ReadFileTool


def _build_test_config(tmp_path: Path) -> Any:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        agent=SimpleNamespace(
            workspace=workspace,
            systemPrompt="You are a safe assistant. Never invent tool results.",
            maxIterations=4,
            maxHistory=12,
        ),
        storage=SimpleNamespace(sessionFile=workspace / "sessions.json"),
        tools=SimpleNamespace(
            time=SimpleNamespace(enabled=False),
            readFile=SimpleNamespace(enabled=False, rootDir=workspace),
            shell=SimpleNamespace(enabled=False),
            web=SimpleNamespace(enabled=False, maxChars=12000),
        ),
    )


class ScriptedProvider:
    """Deterministic provider for agent-loop tests."""

    def __init__(self, scripted: list[LLMResponse]):
        self._scripted = scripted
        self.calls: list[dict[str, Any]] = []

    async def generate(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        self.calls.append({"messages": copy.deepcopy(messages), "tools": copy.deepcopy(tools)})
        if not self._scripted:
            return LLMResponse(content="No scripted response.", tool_calls=[])
        return self._scripted.pop(0)


class FailingTool:
    name = "failing_tool"
    definition = {
        "type": "function",
        "function": {
            "name": "failing_tool",
            "description": "Always fails for test",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    }

    async def run(self, **kwargs: Any) -> str:
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_unknown_tool_error_is_exposed_to_model_context(tmp_path: Path) -> None:
    provider = ScriptedProvider(
        [
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="c1", name="missing_tool", arguments={})],
            ),
            LLMResponse(content="I could not run the tool.", tool_calls=[]),
        ]
    )
    agent = AgentLoop(config=_build_test_config(tmp_path), provider=provider, bus=None)

    inbound = InboundMessage(
        channel="test",
        sender_id="u1",
        chat_id="c1",
        content="Run a tool that does not exist",
        metadata={},
    )
    reply = await agent.process_message(inbound)

    assert "could not run" in reply.lower()
    second_turn_messages = provider.calls[1]["messages"]
    tool_frames = [m for m in second_turn_messages if m.get("role") == "tool"]
    assert tool_frames
    assert "does not exist" in tool_frames[-1]["content"]


@pytest.mark.asyncio
async def test_tool_exception_is_not_hidden_from_followup_turn(tmp_path: Path) -> None:
    provider = ScriptedProvider(
        [
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="c2", name="failing_tool", arguments={})],
            ),
            LLMResponse(content="Tool failed, I cannot claim success.", tool_calls=[]),
        ]
    )
    agent = AgentLoop(config=_build_test_config(tmp_path), provider=provider, bus=None)
    agent.tools.register(FailingTool())

    inbound = InboundMessage(
        channel="test",
        sender_id="u1",
        chat_id="c2",
        content="Do the failing action",
        metadata={},
    )
    reply = await agent.process_message(inbound)

    assert "cannot claim success" in reply.lower()
    tool_frames = [m for m in provider.calls[1]["messages"] if m.get("role") == "tool"]
    assert tool_frames
    assert "execution failed" in tool_frames[-1]["content"]


@pytest.mark.asyncio
async def test_empty_turn_gets_internal_nudge_instead_of_fake_answer(tmp_path: Path) -> None:
    provider = ScriptedProvider(
        [
            LLMResponse(content="", tool_calls=[]),
            LLMResponse(content="Final answer after nudge.", tool_calls=[]),
        ]
    )
    agent = AgentLoop(config=_build_test_config(tmp_path), provider=provider, bus=None)

    inbound = InboundMessage(
        channel="test",
        sender_id="u1",
        chat_id="c3",
        content="Say something",
        metadata={},
    )
    reply = await agent.process_message(inbound)

    assert "final answer" in reply.lower()
    second_turn_messages = provider.calls[1]["messages"]
    assert second_turn_messages[-1]["role"] == "user"
    assert "please provide a concise final answer" in second_turn_messages[-1]["content"].lower()


@pytest.mark.asyncio
async def test_mcp_wrapper_returns_session_closed_message(tmp_path: Path) -> None:
    class FakeSession:
        async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
            raise ClosedResourceError

    tool_def = SimpleNamespace(
        name="API-post-page",
        description="Create page",
        inputSchema={"type": "object", "properties": {}},
    )
    wrapper = MCPToolWrapper(FakeSession(), "notion", tool_def, tool_timeout=5)

    result = await wrapper.run(parent={"workspace": True})
    assert "session closed" in result.lower()


@pytest.mark.asyncio
async def test_read_file_denies_path_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "secret.txt"
    outside.write_text("TOP_SECRET", encoding="utf-8")

    tool = ReadFileTool(root_dir=workspace)
    result = await tool.run(path="../secret.txt")

    assert result == "Access denied."


@pytest.mark.asyncio
async def test_read_file_missing_file_does_not_fabricate_content(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    tool = ReadFileTool(root_dir=workspace)

    result = await tool.run(path="not_exists.md")
    assert result == "File not found."
