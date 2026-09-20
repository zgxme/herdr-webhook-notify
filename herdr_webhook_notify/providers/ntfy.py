"""ntfy push notification."""

from __future__ import annotations

from .base import Delivery, option, require

NAME = "ntfy"
TITLE = "ntfy"
FLAVOR = "plain"
CONFIG_KEYS = ("topic", "url", "token", "priority", "tags", "click")
DEFAULT_SERVER = "https://ntfy.sh"

_PRIORITY = {"done": "default", "blocked": "high", "unknown": "high", "exited": "high", "test": "low"}


def validate(options: dict) -> None:
    require(options, ("topic",), NAME)


def flavor(options: dict) -> str:  # noqa: ARG001
    return FLAVOR


def build(options: dict, message) -> Delivery:
    server = option(options, "url", DEFAULT_SERVER).rstrip("/")
    url = f"{server}/{option(options, 'topic')}"
    headers = {
        "Title": message.title[:250],
        "Priority": option(options, "priority") or _PRIORITY.get(message.kind, "default"),
        "Content-Type": "text/plain; charset=utf-8",
    }
    tags = option(options, "tags")
    if tags:
        headers["Tags"] = tags
    click = option(options, "click")
    if click:
        headers["Click"] = click
    token = option(options, "token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = f"{message.title}\n{message.body}".encode()
    return Delivery(NAME, url, body, headers, "push notification")
