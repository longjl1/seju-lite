import json
import os
import re
from pathlib import Path
from .schema import RootConfig


_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _expand_env(value):
    if isinstance(value, str):
        def repl(match):
            key = match.group(1)
            return os.getenv(key, "")
        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def load_config(path: str | Path) -> RootConfig:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    expanded = _expand_env(raw)
    return RootConfig.model_validate(expanded)