"""Provider registry."""

from __future__ import annotations

from . import (
    dingtalk,
    discord,
    feishu,
    generic,
    google_chat,
    lark,
    ntfy,
    slack,
    teams,
    telegram,
    wecom,
)

MODULES = (
    dingtalk,
    discord,
    feishu,
    generic,
    google_chat,
    lark,
    ntfy,
    slack,
    teams,
    telegram,
    wecom,
)

REGISTRY = {module.NAME: module for module in MODULES}


def names() -> list:
    return sorted(REGISTRY)


def get(name: str):
    return REGISTRY.get(name)


__all__ = ["REGISTRY", "MODULES", "names", "get"]
