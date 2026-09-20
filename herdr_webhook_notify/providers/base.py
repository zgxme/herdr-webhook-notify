"""Shared helpers for webhook providers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


class ProviderError(Exception):
    """Raised when a provider is misconfigured."""


@dataclass
class Message:
    """A rendered notification, ready for a provider to wrap."""

    kind: str
    status: str
    title: str
    body: str
    fields: dict = field(default_factory=dict)
    timestamp: int = 0


@dataclass
class Delivery:
    """An HTTP request a provider wants to send."""

    provider: str
    url: str
    body: bytes
    headers: dict = field(default_factory=dict)
    summary: str = ""


COLORS = {
    "done": "green",
    "blocked": "orange",
    "unknown": "red",
    "exited": "red",
    "test": "blue",
}

HEX_COLORS = {
    "done": "2EB67D",
    "blocked": "ECB22E",
    "unknown": "E01E5A",
    "exited": "E01E5A",
    "test": "4A90D9",
}

DISCORD_COLORS = {
    "done": 0x2EB67D,
    "blocked": 0xECB22E,
    "unknown": 0xE01E5A,
    "exited": 0xE01E5A,
    "test": 0x4A90D9,
}


def color_for(kind: str) -> str:
    return COLORS.get(kind, "blue")


def hex_color_for(kind: str) -> str:
    return HEX_COLORS.get(kind, "4A90D9")


def discord_color_for(kind: str) -> int:
    return DISCORD_COLORS.get(kind, 0x4A90D9)


def require(options: dict, keys, provider: str) -> None:
    missing = [key for key in keys if not str(options.get(key) or "").strip()]
    if missing:
        raise ProviderError(
            f"{provider}: missing required option(s): {', '.join(missing)}"
        )


def option(options: dict, key: str, default: str = "") -> str:
    value = options.get(key)
    if value is None:
        return default
    return str(value).strip()


def json_bytes(payload) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def json_headers() -> dict:
    return {"Content-Type": "application/json; charset=utf-8"}


def flavor(options: dict) -> str:  # noqa: ARG001 - default implementation
    return "markdown"
