"""Telegram bot API sender."""

from __future__ import annotations

import html
import re

from .base import Delivery, json_bytes, json_headers, option, require

NAME = "telegram"
TITLE = "Telegram"
FLAVOR = "plain"
CONFIG_KEYS = (
    "bot_token",
    "chat_id",
    "parse_mode",
    "message_thread_id",
    "disable_notification",
    "api_base",
)
_API_BASE = "https://api.telegram.org"
_MARKDOWN_V2_RESERVED = re.compile(r"([_*\[\]()~`>#+\-=|{}.!])")


def validate(options: dict) -> None:
    require(options, ("bot_token", "chat_id"), NAME)
    parse_mode = option(options, "parse_mode")
    if parse_mode and parse_mode not in ("HTML", "MarkdownV2"):
        raise ValueError(f"{NAME}: parse_mode must be HTML or MarkdownV2")


def flavor(options: dict) -> str:
    # Escaping happens in build(), so the template keeps its Markdown markers.
    return "markdown"


def _escape_markdown_v2(text: str) -> str:
    placeholder = "\x00"
    text = text.replace("**", placeholder)
    text = _MARKDOWN_V2_RESERVED.sub(r"\\\1", text)
    return text.replace(placeholder, "*")


def build(options: dict, message) -> Delivery:
    text = f"{message.title}\n{message.body}"
    payload = {
        "chat_id": option(options, "chat_id"),
        "text": text,
        "disable_web_page_preview": True,
    }
    parse_mode = option(options, "parse_mode")
    if parse_mode == "HTML":
        payload["parse_mode"] = "HTML"
        payload["text"] = html.escape(text)
    elif parse_mode == "MarkdownV2":
        payload["parse_mode"] = "MarkdownV2"
        payload["text"] = _escape_markdown_v2(text)

    thread_id = option(options, "message_thread_id")
    if thread_id:
        payload["message_thread_id"] = int(thread_id)
    if option(options, "disable_notification").lower() in ("1", "true", "yes", "on"):
        payload["disable_notification"] = True

    url = f"{option(options, 'api_base', _API_BASE)}/bot{option(options, 'bot_token')}/sendMessage"
    return Delivery(NAME, url, json_bytes(payload), json_headers(), "sendMessage")
