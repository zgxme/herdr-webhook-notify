"""Lark (Feishu international) custom bot webhook.

Lark speaks the same custom-bot protocol as Feishu: the same JSON payload, the
same optional signing algorithm. This provider reuses that implementation and
only changes its identity, so `herdr-webhook-notify.status` and the docs name
the service the user actually configured.
"""

from __future__ import annotations

from . import feishu
from .base import Delivery

NAME = "lark"
TITLE = "Lark"
FLAVOR = feishu.FLAVOR
CONFIG_KEYS = feishu.CONFIG_KEYS
DEFAULT_HOST = "open.larksuite.com"


def validate(options: dict) -> None:
    feishu.validate(options)


def sign(secret: str, timestamp: int) -> str:
    return feishu.sign(secret, timestamp)


def build(options: dict, message) -> Delivery:
    delivery = feishu.build(options, message)
    return Delivery(
        NAME,
        delivery.url,
        delivery.body,
        delivery.headers,
        f"{delivery.summary} (Lark)",
    )
