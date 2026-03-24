from __future__ import annotations

from collections.abc import Callable


class CommandRouter:
    """Handle command-style user inputs before normal agent processing."""

    def __init__(
        self,
        *,
        sessions,
        subagents,
        schedule_restart: Callable[[], None],
        schedule_archive: Callable[[list[dict]], None],
    ):
        self.sessions = sessions
        self.subagents = subagents
        self._schedule_restart = schedule_restart
        self._schedule_archive = schedule_archive

    async def handle(self, *, content: str, session) -> str | None:
        cmd = (content or "").strip().lower()
        if not cmd.startswith("/"):
            return None

        if cmd == "/restart":
            self._schedule_restart()
            return "Restarting..."

        if cmd == "/stop":
            cancelled = await self.subagents.cancel_by_session(session.key)
            return f"Stopped {cancelled} task(s)." if cancelled else "No active task to stop."

        if cmd == "/help":
            lines = [
                "seju-lite commands:",
                "/new - Start a new conversation (reset short-term session history)",
                "/stop - Stop the current task",
                "/restart - Restart the bot",
                "/help - Show available commands",
            ]
            return "\n".join(lines)

        if cmd == "/new":
            # Preserve long-term memory, reset only short-term session history.
            snapshot = session.messages[session.last_consolidated :]
            session.clear()
            self.sessions.save(session)
            self.sessions.invalidate(session.key)
            if snapshot:
                self._schedule_archive(snapshot)
            return "New session started. Short-term history has been reset."

        return None
