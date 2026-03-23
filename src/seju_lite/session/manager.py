import json
import re
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class Session(BaseModel):
    key: str
    messages: list[dict] = Field(default_factory=list)
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_consolidated: int = 0

    def get_history(self, max_messages: int = 12) -> list[dict]:
        unconsolidated = self.messages[self.last_consolidated:]
        if max_messages <= 0:
            return unconsolidated
        return unconsolidated[-max_messages:]

    def clear(self) -> None:
        self.messages = []
        self.last_consolidated = 0
        self.updated_at = datetime.now().isoformat()


class SessionManager:
    def __init__(self, session_file: Path) -> None:
        self.session_file = session_file
        self.sessions_dir = self._derive_sessions_dir(session_file)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, Session] = {}
        self._migrate_legacy_sessions_file()

    @staticmethod
    def _derive_sessions_dir(session_file: Path) -> Path:
        # Backward compatibility: "./workspace/sessions.json" -> "./workspace/sessions/"
        return session_file if session_file.suffix == "" else session_file.parent / session_file.stem

    @staticmethod
    def _safe_key(key: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]", "_", key)

    def _session_path(self, key: str) -> Path:
        return self.sessions_dir / f"{self._safe_key(key)}.json"

    def _migrate_legacy_sessions_file(self) -> None:
        # Legacy format: one JSON file containing all sessions by key.
        if not self.session_file.exists() or self.session_file.is_dir():
            return

        text = self.session_file.read_text(encoding="utf-8").strip()
        if not text:
            return

        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            return

        if not isinstance(raw, dict):
            return

        for key, value in raw.items():
            try:
                session = Session.model_validate(value)
            except Exception:
                continue
            session.key = key
            self._sessions[key] = session
            self.save(session)

    def _load_one(self, key: str) -> Session | None:
        path = self._session_path(key)
        if not path.exists():
            return None

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            session = Session.model_validate(raw)
            session.key = key
            return session
        except Exception:
            return None

    def get_or_create(self, key: str) -> Session:
        if key in self._sessions:
            return self._sessions[key]

        loaded = self._load_one(key)
        if loaded is not None:
            self._sessions[key] = loaded
            return loaded

        created = Session(key=key)
        self._sessions[key] = created
        return created

    def save(self, session: Session) -> None:
        session.updated_at = datetime.now().isoformat()
        self._sessions[session.key] = session
        self._session_path(session.key).write_text(
            json.dumps(session.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def clear(self, key: str) -> Session:
        session = self.get_or_create(key)
        session.clear()
        self.save(session)
        return session

    def invalidate(self, key: str) -> None:
        self._sessions.pop(key, None)
