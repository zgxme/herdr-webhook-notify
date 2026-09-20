"""DingTalk custom robot webhook."""

from __future__ import annotations

import base64
import hashlib
import hmac
import urllib.parse

from .base import Delivery, json_bytes, json_headers, option, require

NAME = "dingtalk"
TITLE = "DingTalk"
FLAVOR = "markdown"
CONFIG_KEYS = ("webhook_url", "secret")


def validate(options: dict) -> None:
    require(options, ("webhook_url",), NAME)


def sign(secret: str, timestamp_ms: int) -> str:
    string_to_sign = f"{timestamp_ms}\n{secret}".encode()
    digest = hmac.new(secret.encode("utf-8"), string_to_sign, hashlib.sha256).digest()
    return urllib.parse.quote_plus(base64.b64encode(digest).decode("utf-8"))


def signed_url(webhook_url: str, secret: str, timestamp_ms: int) -> str:
    separator = "&" if "?" in webhook_url else "?"
    return (
        f"{webhook_url}{separator}timestamp={timestamp_ms}"
        f"&sign={sign(secret, timestamp_ms)}"
    )


def build(options: dict, message) -> Delivery:
    url = option(options, "webhook_url")
    secret = option(options, "secret")
    if secret:
        url = signed_url(url, secret, int(message.timestamp * 1000))
    payload = {
        "msgtype": "markdown",
        "markdown": {"title": message.title[:64], "text": message.body},
    }
    return Delivery(NAME, url, json_bytes(payload), json_headers(), "markdown")
