"""WeCom (WeChat Work) group robot webhook."""

from __future__ import annotations

from .base import Delivery, json_bytes, json_headers, option, require

NAME = "wecom"
TITLE = "WeCom group robot"
FLAVOR = "markdown"
CONFIG_KEYS = ("webhook_url", "key", "base_url")
DEFAULT_BASE = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send"


def validate(options: dict) -> None:
    if not option(options, "webhook_url") and not option(options, "key"):
        raise ValueError(f"{NAME}: set webhook_url or key")


def resolve_url(options: dict) -> str:
    url = option(options, "webhook_url")
    if url:
        return url
    return f"{option(options, 'base_url', DEFAULT_BASE)}?key={option(options, 'key')}"


def build(options: dict, message) -> Delivery:
    require(options, ("key",), NAME) if not option(options, "webhook_url") else None
    payload = {
        "msgtype": "markdown",
        "markdown": {"content": f"### {message.title}\n{message.body}"},
    }
    return Delivery(NAME, resolve_url(options), json_bytes(payload), json_headers(), "markdown")
