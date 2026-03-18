from pathlib import Path


class SkillsLoader:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.skills_dir = workspace / "skills"

    def list_skills(self) -> list[dict]:
        items = []
        if not self.skills_dir.exists():
            return items

        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    items.append({
                        "name": skill_dir.name,
                        "path": str(skill_file)
                    })
        return items

    def load_skill(self, name: str) -> str | None:
        path = self.skills_dir / name / "SKILL.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def build_skills_summary(self) -> str:
        skills = self.list_skills()
        if not skills:
            return ""
        lines = ["# Skills"]
        for s in skills:
            lines.append(f"- {s['name']}: {s['path']}")
        return "\n".join(lines)