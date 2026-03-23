from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


def _is_process_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


class InstanceLock:
    """Best-effort single-process lock based on atomic file creation."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fd: int | None = None

    def acquire(self) -> None:
        try:
            self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            existing_pid = self._read_existing_pid()
            if existing_pid and _is_process_running(existing_pid):
                raise RuntimeError(
                    f"seju-lite is already running (pid={existing_pid}). "
                    "Stop the existing process before starting another instance."
                )

            # Stale lock file left by a dead process, remove and retry once.
            self.path.unlink(missing_ok=True)
            self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)

        payload = {
            "pid": os.getpid(),
            "started_at": datetime.now().isoformat(),
            "lock": "seju-lite-start",
        }
        os.write(self._fd, json.dumps(payload).encode("utf-8"))
        os.fsync(self._fd)

    def release(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            finally:
                self._fd = None
        self.path.unlink(missing_ok=True)

    def _read_existing_pid(self) -> int | None:
        try:
            raw = self.path.read_text(encoding="utf-8").strip()
            if not raw:
                return None
            data = json.loads(raw)
            pid = int(data.get("pid"))
            return pid if pid > 0 else None
        except Exception:
            return None
