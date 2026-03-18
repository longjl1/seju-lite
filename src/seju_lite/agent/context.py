from pathlib import Path
from typing import Any
from .memory import MemoryStore
from .skills import SkillsLoader


class ContextBuilder:
    RUNTIME_TAG = "[Runtime Context]"

    def __init__(self, workspace: Path, system_prompt: str):
        self.workspace = workspace
        self.system_prompt = system_prompt
        self.memory = MemoryStore(workspace)
        self.skills = SkillsLoader(workspace)

    def build_system_prompt(self) -> str:
        parts = [self.system_prompt]

        memory = self.memory.get_memory_context()
        if memory:
            parts.append(memory)

        skills = self.skills.build_skills_summary()
        if skills:
            parts.append(skills)

        return "\n\n---\n\n".join(parts)

    def build_runtime_context(self, channel: str, chat_id: str) -> str:
        return f"{self.RUNTIME_TAG}\nChannel: {channel}\nChat ID: {chat_id}"

    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        channel: str,
        chat_id: str,
    ) -> list[dict[str, Any]]:
        runtime = self.build_runtime_context(channel, chat_id)
        merged_user = f"{runtime}\n\n{current_message}"

        return [
            {"role": "system", "content": self.build_system_prompt()},
            *history,
            {"role": "user", "content": merged_user},
        ]