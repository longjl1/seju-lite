import asyncio
import inspect
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

from seju_lite.agent.command_router import CommandRouter
from seju_lite.agent.context import ContextBuilder
from seju_lite.agent.context_policy import ContextPolicyDecider
from seju_lite.agent.context_utils import filter_low_signal_history
from seju_lite.agent.memory import MemoryConsolidator
from seju_lite.agent.subagent import SubagentManager
from seju_lite.session.manager import SessionManager
from seju_lite.tools.message_helper import MessageHelperTool
from seju_lite.tools.read_file_tool import ReadFileTool
from seju_lite.tools.registry import ToolRegistry
from seju_lite.tools.simple_rag_tool import (
    EmbeddedRagAnswerTool,
    EmbeddedRagIngestTool,
    EmbeddedRagRetrieveTool,
    EmbeddedSimpleRAGRuntime,
)
from seju_lite.tools.spawn_tool import SpawnTool
from seju_lite.tools.time_tool import TimeTool
from seju_lite.tools.web_tool import WebFetchTool

"""
The core processing engine.

1. Receives messages from the bus
2. Builds context with history/memory/skills
3. Calls the LLM
4. Executes tool calls (including spawn)
5. Saves session turns
"""


class AgentLoop:
    _INTERNAL_NUDGE = (
        "Please provide a concise final answer to the user based on the "
        "tool results and conversation context."
    )

    def __init__(self, config, provider, bus):
        self.config = config
        self.provider = provider
        self.bus = bus
        self.workspace = Path(config.agent.workspace)
        self.logger = logging.getLogger("seju_lite.agent")

        self.context = ContextBuilder(
            workspace=self.workspace,
            system_prompt=config.agent.systemPrompt,
        )
        self.context_policy = ContextPolicyDecider(
            default_history_limit=self.config.agent.maxHistory
        )
        self.sessions = SessionManager(config.storage.sessionFile)
        self.memory_consolidator = MemoryConsolidator(
            workspace=self.workspace,
            sessions=self.sessions,
            provider=self.provider,
            max_history=self.config.agent.maxHistory,
        )

        self.tools = ToolRegistry()
        self.simple_rag_runtime = EmbeddedSimpleRAGRuntime(workspace=self.workspace)
        subagent_iterations = getattr(config.agent, "subagentMaxIterations", 10)
        self.subagents = SubagentManager(
            provider=provider,
            bus=bus,
            tools=self.tools,
            max_iterations=subagent_iterations,
        )
        self._register_tools()
        self._background_tasks: list[asyncio.Task] = []
        self.command_router = CommandRouter(
            sessions=self.sessions,
            subagents=self.subagents,
            schedule_restart=lambda: asyncio.create_task(self._restart_process()),
            schedule_archive=lambda snapshot: self._schedule_background(
                self._archive_snapshot(snapshot)
            ),
        )

    def _register_tools(self):
        def _register_if_missing(tool) -> None:
            if self.tools.get(tool.name) is None:
                self.tools.register(tool)

        if self.config.tools.time.enabled:
            _register_if_missing(TimeTool())
        if self.config.tools.readFile.enabled:
            _register_if_missing(ReadFileTool(Path(self.config.tools.readFile.rootDir)))
        if self.config.tools.web.enabled:
            _register_if_missing(WebFetchTool(max_chars=self.config.tools.web.maxChars))
        _register_if_missing(EmbeddedRagIngestTool(self.simple_rag_runtime))
        _register_if_missing(EmbeddedRagRetrieveTool(self.simple_rag_runtime))
        _register_if_missing(EmbeddedRagAnswerTool(self.simple_rag_runtime))

        # Subagent is tool-driven (spawn tool), not implicit routing.
        if getattr(self.config.agent, "enableSubagent", True):
            _register_if_missing(SpawnTool(self.subagents))
            _register_if_missing(MessageHelperTool(self.subagents))

    @staticmethod
    def _to_openai_tool_call_dict(tc) -> dict:
        return {
            "id": tc.id,
            "type": "function",
            "function": {
                "name": tc.name,
                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
            },
        }

    def _set_tool_context(
        self,
        channel: str,
        chat_id: str,
        session_key: str,
        metadata: dict | None = None,
    ) -> None:
        spawn = self.tools.get("spawn")
        if spawn and hasattr(spawn, "set_context"):
            spawn.set_context(channel=channel, chat_id=chat_id, session_key=session_key)
        helper = self.tools.get("message_helper")
        if helper and hasattr(helper, "set_context"):
            helper.set_context(session_key=session_key)
        for tool in self.tools.iter_tools():
            if hasattr(tool, "set_context"):
                if tool is spawn or tool is helper:
                    continue
                params = inspect.signature(tool.set_context).parameters
                kwargs: dict[str, object] = {}
                if "channel" in params:
                    kwargs["channel"] = channel
                if "chat_id" in params:
                    kwargs["chat_id"] = chat_id
                if "session_key" in params:
                    kwargs["session_key"] = session_key
                if "metadata" in params:
                    kwargs["metadata"] = metadata or {}
                if kwargs:
                    tool.set_context(**kwargs)

    async def _restart_process(self) -> None:
        await asyncio.sleep(1)
        os.execv(sys.executable, [sys.executable, "-m", "seju_lite", *sys.argv[1:]])

    # handle threaded execution 
    def _schedule_background(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._background_tasks.append(task)
        task.add_done_callback(self._background_tasks.remove)

    async def _archive_snapshot(self, snapshot: list[dict]) -> None:
        await self.memory_consolidator.archive_messages(snapshot)

    @staticmethod
    def _extract_tool_name(tool_def: dict) -> str:
        return str(tool_def.get("function", {}).get("name", "")).strip()

    def _filter_tool_defs(self, allowed_tool_names: set[str] | None) -> list[dict]:
        defs = self.tools.get_definitions()
        if not allowed_tool_names:
            return defs
        return [d for d in defs if self._extract_tool_name(d) in allowed_tool_names]

    @staticmethod
    def _preview_payload(value: object, limit: int = 300) -> str:
        if isinstance(value, str):
            preview = value
        else:
            preview = json.dumps(value, ensure_ascii=False)
        preview = preview.replace("\n", " ")
        if len(preview) > limit:
            preview = preview[:limit] + "...(truncated)"
        return preview

    async def _run_agent_loop(
        self,
        messages,
        allowed_tool_names: set[str] | None = None,
        event_callback: Callable[[dict], Awaitable[None]] | None = None,
    ):
        max_iterations = self.config.agent.maxIterations
        final_content = None
        tool_defs = self._filter_tool_defs(allowed_tool_names)

        for idx in range(max_iterations):
            self.logger.info("Agent loop iteration %s/%s", idx + 1, max_iterations)
            if event_callback:
                await event_callback(
                    {
                        "type": "status",
                        "id": f"iteration-{idx + 1}",
                        "title": f"Iteration {idx + 1}/{max_iterations}",
                        "detail": "Planning the next action.",
                        "state": "info",
                    }
                )
            response = await self.provider.generate(
                messages=messages,
                tools=tool_defs,
            )

            if response.has_tool_calls:
                self.logger.info(
                    "LLM requested %s tool call(s): %s",
                    len(response.tool_calls),
                    ", ".join(tc.name for tc in response.tool_calls),
                )
                tool_calls = [self._to_openai_tool_call_dict(tc) for tc in response.tool_calls]
                messages = self.context.add_assistant_message(
                    messages=messages,
                    content=response.content,
                    tool_calls=tool_calls,
                )

                for tc in response.tool_calls:
                    args_preview = self._preview_payload(tc.arguments, limit=500)
                    self.logger.info("Calling tool: %s args=%s", tc.name, args_preview)
                    if event_callback:
                        await event_callback(
                            {
                                "type": "tool_call",
                                "id": tc.id,
                                "tool_name": tc.name,
                                "title": f"Calling {tc.name}",
                                "detail": args_preview,
                                "state": "pending",
                            }
                        )
                    if allowed_tool_names and tc.name not in allowed_tool_names:
                        result = (
                            f"Tool '{tc.name}' is not available in this agent profile. "
                            "Choose a permitted tool or provide a direct response."
                        )
                    else:
                        result = await self.tools.execute(tc.name, tc.arguments)
                    result_preview = self._preview_payload(result)
                    self.logger.info("Tool finished: %s result=%s", tc.name, result_preview)
                    if event_callback:
                        await event_callback(
                            {
                                "type": "tool_result",
                                "id": tc.id,
                                "tool_name": tc.name,
                                "title": f"{tc.name} finished",
                                "detail": result_preview,
                                "state": "error"
                                if result.startswith("Tool '") or result.startswith("Error ")
                                else "done",
                            }
                        )
                    messages = self.context.add_tool_result(
                        messages=messages,
                        tool_call_id=tc.id,
                        tool_name=tc.name,
                        result=result,
                    )
            else:
                self.logger.info("LLM returned no tool calls in this iteration")
                if response.content and response.content.strip():
                    final_content = response.content
                    if event_callback:
                        await event_callback(
                            {
                                "type": "status",
                                "id": "drafting-final-answer",
                                "title": "Drafting final answer",
                                "detail": "Converting the gathered context into a reply.",
                                "state": "done",
                            }
                        )
                    messages = self.context.add_assistant_message(
                        messages=messages,
                        content=final_content,
                    )
                    break

                messages.append(
                    {
                        "role": "user",
                        "content": self._INTERNAL_NUDGE,
                    }
                )

        return final_content or "No response.", messages

    def _save_turn(self, session, messages: list[dict], skip: int) -> None:
        for m in messages[skip:]:
            role = m.get("role")
            content = m.get("content")

            if role == "assistant":
                if m.get("tool_calls"):
                    continue
                if not isinstance(content, str) or not content.strip():
                    continue
                entry = {"role": "assistant", "content": content}
            elif role == "user":
                if not isinstance(content, str) or not content.strip():
                    continue
                if content == self._INTERNAL_NUDGE:
                    continue
                if content.startswith(ContextBuilder._RUNTIME_CONTEXT_TAG):
                    parts = content.split("\n\n", 1)
                    if len(parts) > 1 and parts[1].strip():
                        content = parts[1]
                    else:
                        continue
                entry = {"role": "user", "content": content}
            else:
                continue

            entry.setdefault("timestamp", datetime.now().isoformat())
            session.messages.append(entry)

    async def process_message(
        self,
        inbound,
        tool_allowlist: set[str] | None = None,
        event_callback: Callable[[dict], Awaitable[None]] | None = None,
    ):
        workflow_internal = bool(inbound.metadata.get("workflow_internal"))
        session = self.sessions.get_or_create(inbound.session_key)
        if inbound.metadata:
            session.metadata.update(inbound.metadata)
        if not workflow_internal:
            command_result = await self.command_router.handle(content=inbound.content, session=session)
            if command_result is not None:
                return command_result

        # auto consolidation based on num of unconsolidated msg 
        if not workflow_internal:
            await self.memory_consolidator.auto_consolidate(session)

        policy = self.context_policy.decide(inbound.content)
        history = (
            session.get_history(policy.history_limit)
            if policy.include_history
            else []
        )
        history = filter_low_signal_history(history)

        self._set_tool_context(
            channel=inbound.channel,
            chat_id=inbound.chat_id,
            session_key=inbound.session_key,
            metadata=session.metadata,
        )

        messages = self.context.build_messages(
            history=history,
            current_message=inbound.content,
            channel=inbound.channel,
            chat_id=inbound.chat_id,
            metadata=inbound.metadata,
            include_memory=policy.include_memory,
            include_skills=policy.include_skills,
        )

        final_content, all_messages = await self._run_agent_loop(
            messages,
            allowed_tool_names=tool_allowlist,
            event_callback=event_callback,
        )

        if not workflow_internal:
            self._save_turn(session, all_messages, skip=1 + len(history)) # skip system prompt and history
            self.sessions.save(session)
            self._schedule_background(self.memory_consolidator.auto_consolidate(session))
        return final_content
