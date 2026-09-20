"""Template rendering with safe placeholders and empty-line cleanup."""

from __future__ import annotations

import re

# A line that only holds "**Label**:" and no value is dropped from the message.
_LABEL_ONLY = re.compile(r"^\W*[\w\u4e00-\u9fff][\w\s\u4e00-\u9fff]*\W*[:：]\s*$")


class SafeDict(dict):
    """Leave unknown placeholders untouched instead of raising KeyError."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render(template: str, values: dict) -> str:
    if not template:
        return ""
    return template.format_map(SafeDict(values))


def drop_empty_lines(text: str) -> str:
    kept = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _LABEL_ONLY.match(stripped):
            continue
        kept.append(line.rstrip())
    return "\n".join(kept)


def format_duration(seconds) -> str:
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return ""
    total = int(round(seconds))
    if total < 60:
        return f"{total}s"
    minutes, rest = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m{rest:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"
