"""Slack incoming webhook."""

from __future__ import annotations

from .base import Delivery, json_bytes, json_headers, option, require

NAME = "slack"
TITLE = "Slack"
FLAVOR = "slack"
CONFIG_KEYS = ("webhook_url",)


def validate(options: dict) -> None:
    require(options, ("webhook_url",), NAME)


def flavor(options: dict) -> str:  # noqa: ARG001
    return FLAVOR


def build(options: dict, message) -> Delivery:
    payload = {
        "text": f"{message.title}\n{message.body}",
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{message.title}*\n{message.body}"},
            }
        ],
    }
    return Delivery(NAME, option(options, "webhook_url"), json_bytes(payload), json_headers(), "blocks")
