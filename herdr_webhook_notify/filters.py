"""Scope, quiet hours, duration and cooldown rules."""

from __future__ import annotations

import fnmatch
from datetime import datetime


def matches(patterns, value: str) -> bool:
    if not patterns:
        return False
    target = (value or "").lower()
    return any(fnmatch.fnmatch(target, str(pattern).lower()) for pattern in patterns)


def in_quiet_hours(ranges, when: datetime) -> bool:
    minutes = when.hour * 60 + when.minute
    for start, end in ranges:
        if start == end:
            continue
        if start < end:
            if start <= minutes < end:
                return True
        elif minutes >= start or minutes < end:  # overnight range
            return True
    return False


def scope(rules: dict, fields: dict):
    """Apply include/exclude workspace, tab and agent lists. Empty lists allow all.

    ``rules`` is the ``[notify]`` table or a single provider instance's options.
    """
    for kind, key in (("workspace", "workspaces"), ("tab", "tabs"), ("agent", "agents")):
        value = fields.get(kind) or ""
        include = rules.get(f"include_{key}") or []
        if include and not matches(include, value):
            return False, f"{kind} '{value}' is not in include_{key}"
        if matches(rules.get(f"exclude_{key}") or [], value):
            return False, f"{kind} '{value}' is in exclude_{key}"
    return True, ""


def evaluate(config, decision, fields: dict, entry: dict, now: float, when: datetime):
    """Return (allowed, reason). ``reason`` explains a skip."""
    notify = config.notify

    if decision.kind not in notify["events"]:
        return False, f"event kind '{decision.kind}' is not enabled"

    if decision.watched and not notify["notify_when_focused"]:
        return False, "pane was being watched and notify_when_focused is false"

    allowed, reason = scope(notify, fields)
    if not allowed:
        return False, reason

    exempt = decision.kind in (notify["quiet_hours_exempt"] or [])
    if notify["quiet_ranges"] and not exempt and in_quiet_hours(notify["quiet_ranges"], when):
        return False, "inside quiet_hours"

    minimum = float(notify["min_turn_seconds"] or 0)
    if minimum > 0 and decision.kind in ("done", "blocked", "unknown"):
        duration = fields.get("duration_seconds")
        if isinstance(duration, (int, float)) and duration < minimum:
            return False, f"turn lasted {duration:.0f}s, below min_turn_seconds={minimum:g}"

    cooldown = float(notify["cooldown_seconds"] or 0)
    if cooldown > 0:
        last = (entry.get("last_notified") or {}).get(decision.kind)
        if isinstance(last, (int, float)) and now - last < cooldown:
            return False, f"same kind sent {now - last:.0f}s ago (cooldown {cooldown:g}s)"

    return True, ""
