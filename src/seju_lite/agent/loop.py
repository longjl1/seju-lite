import json
import logging
from datetime import datetime
from pathlib import Path

from seju_lite.agent.context import ContextBuilder
from seju_lite.agent.subagent import SubagentManager
from seju_lite.tools.message_helper import MessageHelperTool
from seju_lite.session.manager import SessionManager
from seju_lite.tools.read_file_tool import ReadFileTool
from seju_lite.tools.registry import ToolRegistry
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
        self.sessions = SessionManager(config.storage.sessionFile)

        self.tools = ToolRegistry()
        subagent_iterations = getattr(config.agent, "subagentMaxIterations", 10)
        self.subagents = SubagentManager(
            provider=provider,
            bus=bus,
            tools=self.tools,
            max_iterations=subagent_iterations,
        )
        self._register_tools()

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
        ''' 2026.3.20 add more later '''

        #  subagent is tool-driven (spawn tool), not implicit routing.
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

    def _set_tool_context(self, channel: str, chat_id: str, session_key: str) -> None:
        spawn = self.tools.get("spawn")
        if spawn and hasattr(spawn, "set_context"):
            spawn.set_context(channel=channel, chat_id=chat_id, session_key=session_key)
        helper = self.tools.get("message_helper")
        if helper and hasattr(helper, "set_context"):
            helper.set_context(session_key=session_key)

    async def _run_agent_loop(self, messages):
        max_iterations = self.config.agent.maxIterations
        final_content = None

        for idx in range(max_iterations):
            self.logger.info("Agent loop iteration %s/%s", idx + 1, max_iterations)
            response = await self.provider.generate(
                messages=messages,
                tools=self.tools.get_definitions(),
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
                    args_preview = json.dumps(tc.arguments, ensure_ascii=False)
                    if len(args_preview) > 500:
                        args_preview = args_preview[:500] + "...(truncated)"
                    self.logger.info("Calling tool: %s args=%s", tc.name, args_preview)
                    result = await self.tools.execute(tc.name, tc.arguments)
                    result_preview = result.replace("\n", " ")
                    if len(result_preview) > 300:
                        result_preview = result_preview[:300] + "...(truncated)"
                    self.logger.info("Tool finished: %s result=%s", tc.name, result_preview)
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
    
    # 处理msg 
    async def process_message(self, inbound):
        # Nanobot-aligned command: stop session background tasks.
        # if inbound.content.strip().lower() == "/stop":
        #     cancelled = await self.subagents.cancel_by_session(inbound.session_key)
        #     return f"Stopped {cancelled} subagent task(s)." if cancelled else "No active subagent task."

        session = self.sessions.get_or_create(inbound.session_key)
        history = session.get_history(self.config.agent.maxHistory)

        self._set_tool_context(
            channel=inbound.channel,
            chat_id=inbound.chat_id,
            session_key=inbound.session_key,
        )

        messages = self.context.build_messages(
            history=history,
            current_message=inbound.content,
            channel=inbound.channel,
            chat_id=inbound.chat_id,
        )

        final_content, all_messages = await self._run_agent_loop(messages)

        self._save_turn(session, all_messages, skip=1 + len(history))
        self.sessions.save(session)
        return final_content


