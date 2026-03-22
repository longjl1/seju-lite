"""Spawn tool for delegating complex tasks to background subagents."""

from __future__ import annotations


class SpawnTool:
    name = "spawn"

    def __init__(self, manager):
        self.manager = manager
        self._channel = "cli"
        self._chat_id = "local"
        self._session_key: str | None = None
        self.definition = {
            "type": "function",
            "function": {
                "name": "spawn",
                "description": (
                    "Assign a task to a background subagent when it may require multiple steps, "
                    "file reading, web lookup, or any other independent executions... Use this whenever offloading "
                    "the task would keep the main conversation responsive and report the result when it finished."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "Detailed task for the subagent to execute.",
                        },
                        "label": {
                            "type": "string",
                            "description": "Optional short label for tracking the background task.",
                        },
                    },
                    "required": ["task"],
                },
            },
        }

    def set_context(self, channel: str, chat_id: str, session_key: str | None = None) -> None:
        self._channel = channel
        self._chat_id = chat_id
        self._session_key = session_key

    async def run(self, task: str, label: str | None = None) -> str:
        return await self.manager.spawn(
            task=task,
            label=label,
            origin_channel=self._channel,
            origin_chat_id=self._chat_id,
            session_key=self._session_key,
        )
