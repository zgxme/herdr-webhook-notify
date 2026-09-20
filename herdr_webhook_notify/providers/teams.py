"""Microsoft Teams incoming webhook (MessageCard)."""

from __future__ import annotations

from .base import Delivery, hex_color_for, json_bytes, json_headers, option, require

NAME = "teams"
TITLE = "Microsoft Teams"
FLAVOR = "markdown"
CONFIG_KEYS = ("webhook_url",)


def validate(options: dict) -> None:
    require(options, ("webhook_url",), NAME)


def build(options: dict, message) -> Delivery:
    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": hex_color_for(message.kind),
        "summary": message.title[:120],
        "title": message.title[:120],
        "text": message.body.replace("\n", "\n\n"),
    }
    return Delivery(NAME, option(options, "webhook_url"), json_bytes(payload), json_headers(), "MessageCard")
