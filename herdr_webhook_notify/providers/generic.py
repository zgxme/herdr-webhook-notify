"""Generic HTTP webhook for internal gateways and unsupported services."""

from __future__ import annotations

from .base import Delivery, json_bytes, option, require

NAME = "generic"
TITLE = "Generic HTTP"
FLAVOR = "markdown"
CONFIG_KEYS = ("url", "method", "headers", "body", "content_type")


def validate(options: dict) -> None:
    require(options, ("url",), NAME)
    method = option(options, "method", "POST").upper()
    if method not in ("POST", "PUT", "PATCH"):
        raise ValueError(f"{NAME}: method must be POST, PUT or PATCH")


def flavor(options: dict) -> str:
    return option(options, "flavor", FLAVOR) or FLAVOR


def build(options: dict, message) -> Delivery:
    headers = {"Content-Type": option(options, "content_type", "application/json; charset=utf-8")}
    extra = options.get("headers")
    if isinstance(extra, dict):
        for key, value in extra.items():
            headers[str(key)] = str(value)

    template = options.get("body")
    if isinstance(template, str) and template.strip():
        body = template.format_map(
            _safe_values(message)
        ).encode("utf-8")
        summary = "custom body"
    else:
        body = json_bytes(default_payload(message))
        summary = "default JSON body"

    return Delivery(NAME, option(options, "url"), body, headers, summary)


def _safe_values(message) -> dict:
    values = {"title": message.title, "body": message.body, "kind": message.kind, "status": message.status}
    values.update(message.fields)
    return _SafeDict(values)


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def default_payload(message) -> dict:
    return {
        "title": message.title,
        "body": message.body,
        "kind": message.kind,
        "status": message.status,
        "fields": message.fields,
    }
