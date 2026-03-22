"""Helper tool for message-level control actions (e.g., cancel subagent tasks)."""

from __future__ import annotations


class MessageHelperTool:
    name = "message_helper"

    def __init__(self, subagent_manager):
        self._subagent_manager = subagent_manager
        self._session_key: str | None = None
        self.definition = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": (
                    "Control helper for message/session actions. "
                    "Use this to cancel running subagent tasks based on user intent."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["cancel_subtasks"],
                            "description": "Control action to execute.",
                        },
                        "scope": {
                            "type": "string",
                            "enum": ["session", "all"],
                            "default": "session",
                            "description": "Cancel only this session or all sessions.",
                        },
                    },
                    "required": ["action"],
                },
            },
        }

    def set_context(self, session_key: str) -> None:
        self._session_key = session_key

    async def run(self, action: str, scope: str = "session") -> str:
        if action != "cancel_subtasks":
            return f"Unsupported action '{action}'."

        if scope == "all":
            cancelled = await self._subagent_manager.cancel_all()
            return (
                f"Cancelled {cancelled} subagent task(s) across all sessions."
                if cancelled
                else "No active subagent task across all sessions."
            )

        if not self._session_key:
            return "No active session context for cancel_subtasks."

        cancelled = await self._subagent_manager.cancel_by_session(self._session_key)
        return (
            f"Cancelled {cancelled} subagent task(s) for this session."
            if cancelled
            else "No active subagent task in this session."
        )


# Backward-compatible alias for your existing class name.
Message_helper = MessageHelperTool
