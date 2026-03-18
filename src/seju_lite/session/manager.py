import json
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel, Field


class Session(BaseModel):
    key: str
    messages: list[dict] = Field(default_factory=list)
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def get_history(self, max_messages: int = 12) -> list[dict]:
        if max_messages <= 0:
            return self.messages
        return self.messages[-max_messages:]


class SessionManager:
    def __init__(self, session_file: Path) -> None:
        self.session_file = session_file
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, Session] = {}
        self._load()

    def _load(self) -> None:
        if not self.session_file.exists():
            return
        raw = json.loads(self.session_file.read_text(encoding="utf-8"))
        self._sessions = {
            k: Session.model_validate(v)
            for k, v in raw.items()
        }

    def save_all(self) -> None:
        data = {k: v.model_dump() for k, v in self._sessions.items()}
        self.session_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_or_create(self, key: str) -> Session:
        if key not in self._sessions:
            self._sessions[key] = Session(key=key)
        return self._sessions[key]

    def save(self, session: Session) -> None:
        session.updated_at = datetime.now().isoformat()
        self._sessions[session.key] = session
        self.save_all()