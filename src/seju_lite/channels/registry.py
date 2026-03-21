from __future__ import annotations

import importlib
import pkgutil
from importlib.metadata import entry_points
from typing import Any

from seju_lite.channels.base import BaseChannel

_INTERNAL = frozenset({"base", "registry"})


def discover_channel_module_names() -> list[str]:
    import seju_lite.channels as pkg

    return [
        name
        for _, name, ispkg in pkgutil.iter_modules(pkg.__path__)
        if name not in _INTERNAL and not ispkg
    ]


def load_channel_class(module_name: str) -> type[BaseChannel]:
    mod = importlib.import_module(f"seju_lite.channels.{module_name}")
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if isinstance(obj, type) and issubclass(obj, BaseChannel) and obj is not BaseChannel:
            return obj
    raise ImportError(f"No channel class found in seju_lite.channels.{module_name}")


def discover_plugins() -> dict[str, type[BaseChannel]]:
    plugins: dict[str, type[BaseChannel]] = {}
    for ep in entry_points(group="seju_lite.channels"):
        try:
            cls = ep.load()
            if isinstance(cls, type) and issubclass(cls, BaseChannel):
                plugins[ep.name] = cls
        except Exception:
            continue
    return plugins


def discover_all() -> dict[str, type[BaseChannel]]:
    channels: dict[str, type[BaseChannel]] = {}
    for module_name in discover_channel_module_names():
        try:
            cls = load_channel_class(module_name)
        except Exception:
            continue
        key = getattr(cls, "name", module_name) or module_name
        channels[key] = cls
        if module_name.endswith("_bot"):
            channels[module_name.removesuffix("_bot")] = cls

    for name, cls in discover_plugins().items():
        channels.setdefault(name, cls)

    return channels
