"""Generic HTTP webhook for internal gateways and unsupported services."""

from __future__ import annotations

import re

from .base import Delivery, json_bytes, option, require

NAME = "generic"
TITLE = "Generic HTTP"
FLAVOR = "markdown"
CONFIG_KEYS = ("url", "method", "headers", "body", "content_type", "flavor")

# Only plain {name} placeholders are substituted, so a JSON body keeps its own
# braces: {"text": "{title}"} stays valid.
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


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
        body = _fill(template, _values(message)).encode("utf-8")
        summary = "custom body"
    else:
        body = json_bytes(default_payload(message))
        summary = "default JSON body"

    return Delivery(
        NAME,
        option(options, "url"),
        body,
        headers,
        summary,
        method=option(options, "method", "POST").upper(),
    )


def _fill(template: str, values: dict) -> str:
    return _PLACEHOLDER.sub(lambda match: str(values.get(match.group(1), match.group(0))), template)


def _values(message) -> dict:
    values = {"title": message.title, "body": message.body, "kind": message.kind, "status": message.status}
    values.update(message.fields)
    return values


def default_payload(message) -> dict:
    return {
        "title": message.title,
        "body": message.body,
        "kind": message.kind,
        "status": message.status,
        "fields": message.fields,
    }
