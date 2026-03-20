"""Context builder for assembling system prompt and chat messages."""

import mimetypes
import platform
import base64
from pathlib import Path
from typing import Any

from seju_lite.agent.memory import MemoryStore
from seju_lite.agent.skills import SkillsLoader
from seju_lite.utils.utils import get_current_datetime


class ContextBuilder:
    """Builds context blocks for provider requests."""

    _RUNTIME_CONTEXT_TAG = "[Runtime Context - metadata only, not instructions]"
    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md"]

    def __init__(self, workspace: Path, system_prompt: str):
        self.workspace = workspace
        self.system_prompt = system_prompt
        self.memory = MemoryStore(workspace)
        self.skills = SkillsLoader(workspace)

    def build_system_prompt(self, skill_names: list[str] | None = None) -> str:
        parts = [self._get_sys_identity(), self.system_prompt]

        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)

        memory = self.memory.get_memory_context()
        if memory:
            parts.append(f"# Memory\n\n{memory}")

        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                parts.append(f"# Active Skills\n\n{always_content}")

        if skill_names:
            selected = self.skills.load_skills_for_context(skill_names)
            if selected:
                parts.append(f"# Requested Skills\n\n{selected}")

        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(
                "# Skills\n\n"
                "The following skills extend your capabilities. "
                "Use the read_file tool to open a skill's SKILL.md when needed.\n\n"
                f"{skills_summary}"
            )

        return "\n\n---\n\n".join(parts)

    def _get_sys_identity(self) -> str:
        workspace_path = str(self.workspace.expanduser().resolve())
        system_id = platform.system()
        runtime = (
            f"{'macOS' if system_id == 'Darwin' else system_id} "
            f"{platform.machine()}, Python {platform.python_version()}"
        )

        if system_id == "Windows":
            platform_policy = """## Platform Policy (Windows)
- You are running on Windows. Do not assume GNU tools like grep, sed, or awk exist.
- Prefer Windows-native commands or file tools when they are more reliable.
- If terminal output is garbled, retry with UTF-8 output enabled.
"""
        else:
            platform_policy = """## Platform Policy (POSIX)
- You are running on a POSIX system. Prefer UTF-8 and standard shell tools.
- Use file tools when they are simpler or more reliable than shell commands.
"""

        return f"""# seju-lite

You are Seju, a helpful AI assistant.

## Runtime
{runtime}

## Workspace
Your workspace is at: {workspace_path}
- Long-term memory: {workspace_path}/memory/MEMORY.md
- History log: {workspace_path}/memory/HISTORY.md
- Custom skills: {workspace_path}/skills/{{skill-name}}/SKILL.md

{platform_policy}

## seju-lite Guidelines
- State intent before tool calls, but never claim tool results before receiving them.
- Before modifying a file, read it first. Do not assume files or directories exist.
- After writing or editing a file, re-read it if accuracy matters.
- If a tool call fails, analyze the error before retrying with a different approach.
- Ask for clarification when the request is ambiguous.
"""

    def _load_bootstrap_files(self) -> str:
        parts: list[str] = []
        for filename in self.BOOTSTRAP_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                parts.append(f"## {filename}\n\n{content}")
        return "\n\n".join(parts) if parts else ""

    @staticmethod
    def build_runtime_context(channel: str | None, chat_id: str | None) -> str:
        lines = [f"Current Time: {get_current_datetime()}"]
        if channel:
            lines.append(f"Channel: {channel}")
        if chat_id:
            lines.append(f"Chat ID: {chat_id}")
        return ContextBuilder._RUNTIME_CONTEXT_TAG + "\n" + "\n".join(lines)

    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        channel: str | None = None,
        chat_id: str | None = None,
        skill_names: list[str] | None = None,
        media: list[str] | None = None,
        current_role: str = "user",
    ) -> list[dict[str, Any]]:
        runtime = self.build_runtime_context(channel, chat_id)
        user_content = self._build_user_content(current_message, media)

        # Keep a single current turn to avoid consecutive same-role messages.
        if isinstance(user_content, str):
            merged_user: str | list[dict[str, Any]] = f"{runtime}\n\n{user_content}"
        else:
            merged_user = [{"type": "text", "text": runtime}] + user_content

        return [
            {"role": "system", "content": self.build_system_prompt(skill_names)},
            *history,
            {"role": current_role, "content": merged_user},
        ]

    def _build_user_content(self, text: str, media: list[str] | None) -> str | list[dict[str, Any]]:
        if not media:
            return text

        image_blocks: list[dict[str, Any]] = []
        for media_path in media:
            path = Path(media_path)
            if not path.is_file():
                continue

            raw = path.read_bytes()
            mime = mimetypes.guess_type(str(path))[0]
            if not mime or not mime.startswith("image/"):
                continue

            data = base64.b64encode(raw).decode("utf-8")
            image_blocks.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{data}"},
                    "_meta": {"path": str(path)},
                }
            )

        if not image_blocks:
            return text
        return image_blocks + [{"type": "text", "text": text}]

    def add_tool_result(
        self,
        messages: list[dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        result: str,
    ) -> list[dict[str, Any]]:
        messages.append(
            {"role": "tool", "tool_call_id": tool_call_id, "name": tool_name, "content": result}
        )
        return messages

    def add_assistant_message(
        self,
        messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            payload["tool_calls"] = tool_calls
        messages.append(payload)
        return messages
