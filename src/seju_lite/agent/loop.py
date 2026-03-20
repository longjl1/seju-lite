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

    def _register_tools(self):
        if self.config.tools.time.enabled:
            self.tools.register(TimeTool())
        if self.config.tools.readFile.enabled:
            self.tools.register(ReadFileTool(Path(self.config.tools.readFile.rootDir)))

    async def _run_agent_loop(self, messages):
        max_iterations = self.config.agent.maxIterations
        final_content = None

        for _ in range(max_iterations):
            response = await self.provider.generate(
                messages=messages,
                tools=self.tools.get_definitions(),
            )

            if response.has_tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                            }
                        }
                        for tc in response.tool_calls
                    ]
                })

                for tc in response.tool_calls:
                    result = await self.tools.execute(tc.name, tc.arguments)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": result
                    })
            else:
                if response.content and response.content.strip():
                    final_content = response.content
                    messages.append({"role": "assistant", "content": final_content})
                    break

                # Some models occasionally return an empty turn after tool execution.
                # Nudge one more round instead of finishing with "No response.".
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Please provide a concise final answer to the user based on the "
                            "tool results and conversation context."
                        ),
                    }
                )

        return final_content or "No response.", messages

    async def process_message(self, inbound):
        session = self.sessions.get_or_create(inbound.session_key)
        history = session.get_history(self.config.agent.maxHistory)

        messages = self.context.build_messages(
            history=history,
            current_message=inbound.content,
            channel=inbound.channel,
            chat_id=inbound.chat_id
        )

        final_content, all_messages = await self._run_agent_loop(messages)

        new_messages = all_messages[1 + len(history):]
        for m in new_messages:
            m.setdefault("timestamp", datetime.now().isoformat())
            session.messages.append(m)

        self.sessions.save(session)
        return final_content
