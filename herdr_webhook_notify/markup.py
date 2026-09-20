"""Markup flavor helpers.

Templates are written once in Markdown. Providers that expect another dialect
convert the rendered text instead of keeping their own template copy.
"""

from __future__ import annotations

FLAVORS = ("markdown", "slack", "plain")


def convert(text: str, flavor: str = "markdown") -> str:
    if flavor == "slack":
        # Slack mrkdwn uses single asterisks for bold.
        return text.replace("**", "*")
    if flavor == "plain":
        return text.replace("**", "")
    return text
