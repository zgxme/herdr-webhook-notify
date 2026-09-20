"""Feishu / Lark custom bot webhook."""

from __future__ import annotations

import base64
import hashlib
import hmac

from .base import Delivery, json_bytes, json_headers, option, require

NAME = "feishu"
TITLE = "Feishu / Lark"
FLAVOR = "markdown"
CONFIG_KEYS = ("webhook_url", "secret", "format", "card_title_prefix")


def validate(options: dict) -> None:
    require(options, ("webhook_url",), NAME)
    fmt = option(options, "format", "card")
    if fmt not in ("card", "text"):
        raise ValueError(f"{NAME}: format must be card or text")


def sign(secret: str, timestamp: int) -> str:
    string_to_sign = f"{timestamp}\n{secret}".encode()
    digest = hmac.new(string_to_sign, b"", hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def build_card(message, prefix: str) -> dict:
    title = f"{prefix}{message.title}" if prefix else message.title
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": {
                "done": "green",
                "blocked": "orange",
                "unknown": "red",
                "exited": "red",
                "test": "blue",
            }.get(message.kind, "blue"),
            "title": {"tag": "plain_text", "content": title[:120]},
        },
        "elements": [{"tag": "markdown", "content": message.body}],
    }


def build(options: dict, message) -> Delivery:
    payload = {}
    secret = option(options, "secret")
    if secret:
        payload["timestamp"] = str(message.timestamp)
        payload["sign"] = sign(secret, message.timestamp)

    if option(options, "format", "card") == "text":
        payload["msg_type"] = "text"
        payload["content"] = {"text": f"{message.title}\n{message.body}"}
        summary = "text message"
    else:
        payload["msg_type"] = "interactive"
        payload["card"] = build_card(message, option(options, "card_title_prefix"))
        summary = "interactive card"

    return Delivery(NAME, option(options, "webhook_url"), json_bytes(payload), json_headers(), summary)
