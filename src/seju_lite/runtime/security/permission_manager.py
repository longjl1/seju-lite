from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PermissionDecision:
    behavior: str
    reason: str = ""


@dataclass(frozen=True)
class PermissionRule:
    tool: str = "*"
    behavior: str = "deny"
    path: str | None = None
    content: str | None = None


class BashSecurityValidator:
    _DENY_PATTERNS: tuple[tuple[str, str], ...] = (
        ("dangerous_delete", "rm -rf"),
        ("privilege_escalation", "sudo "),
        ("command_substitution", "$("),
        ("shell_control_operator", "&&"),
        ("shell_control_operator", "||"),
        ("shell_control_operator", ";"),
        ("pipeline", "|"),
        ("backticks", "`"),
    )

    def check(self, command: str) -> PermissionDecision | None:
        normalized = (command or "").strip().lower()
        if not normalized:
            return PermissionDecision("deny", "Shell command is empty.")
        for label, marker in self._DENY_PATTERNS:
            if marker in normalized:
                return PermissionDecision(
                    "deny",
                    f"Shell command blocked by validator ({label}: '{marker}').",
                )
        return None


class PermissionManager:
    """Minimal policy layer for tool execution."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        mode: str = "default",
        rules: list[PermissionRule] | None = None,
        workspace: Path | None = None,
    ) -> None:
        self.enabled = enabled
        self.mode = mode
        self.rules = rules or []
        self.workspace = workspace.resolve() if workspace else None
        self._bash_validator = BashSecurityValidator()

    def check(self, tool_name: str, tool_input: dict[str, Any] | None = None) -> PermissionDecision:
        if not self.enabled:
            return PermissionDecision("allow", "Permissions disabled.")

        payload = tool_input or {}
        shell_decision = self._check_shell(tool_name, payload)
        if shell_decision is not None:
            return shell_decision

        path_decision = self._check_path(tool_name, payload)
        if path_decision is not None:
            return path_decision

        for rule in self.rules:
            if self._matches(rule, tool_name, payload):
                return PermissionDecision(
                    rule.behavior,
                    f"Matched {rule.behavior} rule for tool '{tool_name}'.",
                )

        return self._fallback(tool_name)

    def _check_shell(self, tool_name: str, payload: dict[str, Any]) -> PermissionDecision | None:
        if tool_name not in {"shell", "bash"}:
            return None
        command = str(payload.get("command", ""))
        return self._bash_validator.check(command)

    def _check_path(self, tool_name: str, payload: dict[str, Any]) -> PermissionDecision | None:
        if self.workspace is None:
            return None
        raw_path = payload.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            return None

        if tool_name not in {"read_file", "write_file", "edit_file"}:
            return None

        candidate = Path(raw_path)
        resolved = candidate.resolve() if candidate.is_absolute() else (self.workspace / candidate).resolve()
        if resolved == self.workspace or self.workspace in resolved.parents:
            return None
        return PermissionDecision(
            "deny",
            f"Path '{raw_path}' escapes the configured workspace.",
        )

    def _matches(self, rule: PermissionRule, tool_name: str, payload: dict[str, Any]) -> bool:
        if rule.tool not in {"*", tool_name}:
            return False
        if rule.path is not None:
            raw_path = str(payload.get("path", ""))
            if not fnmatch(raw_path, rule.path):
                return False
        if rule.content is not None:
            command = str(payload.get("command", ""))
            if not fnmatch(command, rule.content):
                return False
        return True

    def _fallback(self, tool_name: str) -> PermissionDecision:
        if self.mode == "strict" and tool_name not in {"time", "read_file"}:
            return PermissionDecision(
                "deny",
                f"Tool '{tool_name}' is blocked by strict permission mode.",
            )
        return PermissionDecision("allow", "No matching deny rule.")
