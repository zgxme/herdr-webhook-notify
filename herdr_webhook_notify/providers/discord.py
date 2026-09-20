"""Discord webhook."""

from __future__ import annotations

import time

from .base import Delivery, discord_color_for, json_bytes, json_headers, option, require

NAME = "discord"
TITLE = "Discord"
FLAVOR = "markdown"
CONFIG_KEYS = ("webhook_url", "username", "avatar_url", "content")


def validate(options: dict) -> None:
    require(options, ("webhook_url",), NAME)


def build(options: dict, message) -> Delivery:
    payload = {
        "embeds": [
            {
                "title": message.title[:256],
                "description": message.body[:4000],
                "color": discord_color_for(message.kind),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(message.timestamp)),
            }
        ]
    }
    for key in ("username", "avatar_url", "content"):
        value = option(options, key)
        if value:
            payload[key] = value
    return Delivery(NAME, option(options, "webhook_url"), json_bytes(payload), json_headers(), "embed")
