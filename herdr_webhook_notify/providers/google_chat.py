"""Google Chat incoming webhook."""

from __future__ import annotations

from .base import Delivery, json_bytes, json_headers, option, require

NAME = "google_chat"
TITLE = "Google Chat"
FLAVOR = "slack"
CONFIG_KEYS = ("webhook_url", "thread_key")


def validate(options: dict) -> None:
    require(options, ("webhook_url",), NAME)


def flavor(options: dict) -> str:  # noqa: ARG001
    return FLAVOR


def build(options: dict, message) -> Delivery:
    payload = {"text": f"*{message.title}*\n{message.body}"}
    thread_key = option(options, "thread_key")
    if thread_key:
        payload["thread"] = {"threadKey": thread_key}
    return Delivery(NAME, option(options, "webhook_url"), json_bytes(payload), json_headers(), "text")
