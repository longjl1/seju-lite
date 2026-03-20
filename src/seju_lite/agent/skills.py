"""Skills loader for agent capabilities."""

import json
import os
import re
import shutil
from pathlib import Path

BUILTIN_SKILLS_DIR = Path(__file__).parent.parent / "skills"


class SkillsLoader:
    """Loader for workspace and built-in skills."""

    def __init__(self, workspace: Path, builtin_skills_dir: Path | None = None):
        self.workspace = workspace
        self.workspace_skills = workspace / "skills"
        self.builtin_skills = builtin_skills_dir or BUILTIN_SKILLS_DIR

    def list_skills(self, filter_unavailable: bool = True) -> list[dict[str, str]]:
        skills: list[dict[str, str]] = []

        if self.workspace_skills.exists():
            for skill_dir in self.workspace_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        skills.append(
                            {"name": skill_dir.name, "path": str(skill_file), "source": "workspace"}
                        )

        if self.builtin_skills and self.builtin_skills.exists():
            for skill_dir in self.builtin_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists() and not any(s["name"] == skill_dir.name for s in skills):
                        skills.append(
                            {"name": skill_dir.name, "path": str(skill_file), "source": "builtin"}
                        )

        if filter_unavailable:
            return [s for s in skills if self._check_requirements(self._get_skill_meta(s["name"]))]
        return skills

    def load_skill(self, name: str) -> str | None:
        workspace_skill = self.workspace_skills / name / "SKILL.md"
        if workspace_skill.exists():
            return workspace_skill.read_text(encoding="utf-8")

        if self.builtin_skills:
            builtin_skill = self.builtin_skills / name / "SKILL.md"
            if builtin_skill.exists():
                return builtin_skill.read_text(encoding="utf-8")

        return None

    def load_skills_for_context(self, skill_names: list[str]) -> str:
        parts: list[str] = []
        for name in skill_names:
            content = self.load_skill(name)
            if content:
                parts.append(f"### Skill: {name}\n\n{self._strip_frontmatter(content)}")
        return "\n\n---\n\n".join(parts) if parts else ""

    def build_skills_summary(self) -> str:
        all_skills = self.list_skills(filter_unavailable=False)
        if not all_skills:
            return ""

        def escape_xml(text: str) -> str:
            return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        lines = ["<skills>"]
        for s in all_skills:
            name = escape_xml(s["name"])
            path = s["path"]
            desc = escape_xml(self._get_skill_description(s["name"]))
            meta = self._get_skill_meta(s["name"])
            available = self._check_requirements(meta)

            lines.append(f'  <skill available="{str(available).lower()}">')
            lines.append(f"    <name>{name}</name>")
            lines.append(f"    <description>{desc}</description>")
            lines.append(f"    <location>{path}</location>")

            if not available:
                missing = self._get_missing_requirements(meta)
                if missing:
                    lines.append(f"    <requires>{escape_xml(missing)}</requires>")

            lines.append("  </skill>")
        lines.append("</skills>")
        return "\n".join(lines)

    def get_always_skills(self) -> list[str]:
        result: list[str] = []
        for s in self.list_skills(filter_unavailable=True):
            meta = self.get_skill_metadata(s["name"]) or {}
            skill_meta = self._parse_nanobot_metadata(meta.get("metadata", ""))
            if skill_meta.get("always") or meta.get("always"):
                result.append(s["name"])
        return result

    def get_skill_metadata(self, name: str) -> dict | None:
        content = self.load_skill(name)
        if not content:
            return None

        if content.startswith("---"):
            match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if match:
                metadata: dict[str, str] = {}
                for line in match.group(1).split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip().strip('"\'')
                return metadata
        return None

    def _get_skill_description(self, name: str) -> str:
        meta = self.get_skill_metadata(name)
        if meta and meta.get("description"):
            return meta["description"]
        return name

    def _strip_frontmatter(self, content: str) -> str:
        if content.startswith("---"):
            match = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
            if match:
                return content[match.end():].strip()
        return content

    def _parse_nanobot_metadata(self, raw: str) -> dict:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data.get("nanobot", data.get("openclaw", {}))
            return {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def _check_requirements(self, skill_meta: dict) -> bool:
        requires = skill_meta.get("requires", {})
        for binary in requires.get("bins", []):
            if not shutil.which(binary):
                return False
        for env_var in requires.get("env", []):
            if not os.environ.get(env_var):
                return False
        return True

    def _get_missing_requirements(self, skill_meta: dict) -> str:
        missing: list[str] = []
        requires = skill_meta.get("requires", {})
        for binary in requires.get("bins", []):
            if not shutil.which(binary):
                missing.append(f"CLI: {binary}")
        for env_var in requires.get("env", []):
            if not os.environ.get(env_var):
                missing.append(f"ENV: {env_var}")
        return ", ".join(missing)

    def _get_skill_meta(self, name: str) -> dict:
        meta = self.get_skill_metadata(name) or {}
        return self._parse_nanobot_metadata(meta.get("metadata", ""))
