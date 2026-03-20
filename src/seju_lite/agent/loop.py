import json
from datetime import datetime
from pathlib import Path

from seju_lite.agent.context import ContextBuilder
from seju_lite.session.manager import SessionManager
from seju_lite.tools.registry import ToolRegistry
from seju_lite.tools.time_tool import TimeTool
from seju_lite.tools.read_file_tool import ReadFileTool

"""
    the core processing engine.

    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
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


        # build context
        self.context = ContextBuilder(
            workspace=self.workspace,
            system_prompt=config.agent.systemPrompt
        )

        # build sessions manager
        self.sessions = SessionManager(config.storage.sessionFile)

        # build tools
        self.tools = ToolRegistry()
        self._register_tools()

    # 这里会注册所有的tools 
    def _register_tools(self):
        if self.config.tools.time.enabled:
            self.tools.register(TimeTool())
        if self.config.tools.readFile.enabled:
            self.tools.register(ReadFileTool(Path(self.config.tools.readFile.rootDir)))

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
    

    # core engine
    async def _run_agent_loop(self, messages):
        max_iterations = self.config.agent.maxIterations
        final_content = None

        for _ in range(max_iterations):
            # 调用model
            response = await self.provider.generate(
                messages=messages,
                tools=self.tools.get_definitions(), # see the provider and registry.py [{ type:"...", function:{...} }, ...] 
            )
            # 是否call tools
            if response.has_tool_calls:
                tool_calls = [self._to_openai_tool_call_dict(tc) for tc in response.tool_calls]
                messages = self.context.add_assistant_message(
                    messages=messages,
                    content=response.content,
                    tool_calls=tool_calls,
                )

                for tc in response.tool_calls:
                    result = await self.tools.execute(tc.name, tc.arguments)
                    messages = self.context.add_tool_result(
                        messages=messages,
                        tool_call_id=tc.id,
                        tool_name=tc.name,
                        result=result,
                    )
            else:
                if response.content and response.content.strip():
                    final_content = response.content
                    messages = self.context.add_assistant_message(
                        messages=messages,
                        content=final_content,
                    )
                    break

                # Some models occasionally return an empty turn after tool execution.
                # Nudge one more round instead of finishing with "No response.".
                messages.append(
                    {
                        "role": "user",
                        "content": self._INTERNAL_NUDGE,
                    }
                )

        return final_content or "No response.", messages

    def _sanitize_history_for_model(self, history: list[dict]) -> list[dict]:
        """
        Keep persisted history model-safe for Gemini/OpenAI-style chat.
        We drop internal tool-call frames so truncation cannot break turn order.
        """
        cleaned: list[dict] = []
        for m in history:
            role = m.get("role")
            content = m.get("content")

            if role == "user":
                if isinstance(content, str) and content.strip() and content != self._INTERNAL_NUDGE:
                    cleaned.append({"role": "user", "content": content})
                continue

            if role == "assistant":
                # Do not persist assistant tool-call frames in chat history.
                if m.get("tool_calls"):
                    continue
                if isinstance(content, str) and content.strip():
                    cleaned.append({"role": "assistant", "content": content})
                continue

            # Drop "tool" and unknown roles from persisted history replay.
        return cleaned

    def _save_turn(self, session, messages: list[dict], skip: int) -> None:
        """
        Persist only stable conversational turns and strip runtime metadata prefix.
        """
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

    async def process_message(self, inbound):
        session = self.sessions.get_or_create(inbound.session_key)
        history = session.get_history(self.config.agent.maxHistory)
        # history = self._sanitize_history_for_model(history)

        messages = self.context.build_messages(
            history=history,
            current_message=inbound.content,
            channel=inbound.channel,
            chat_id=inbound.chat_id
        )

        final_content, all_messages = await self._run_agent_loop(messages)

        self._save_turn(session, all_messages, skip=1 + len(history))

        self.sessions.save(session)
        return final_content
