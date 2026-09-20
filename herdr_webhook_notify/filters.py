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


def evaluate(config, decision, fields: dict, entry: dict, now: float, when: datetime):
    """Return (allowed, reason). ``reason`` explains a skip."""
    notify = config.notify

    if decision.kind not in notify["events"]:
        return False, f"event kind '{decision.kind}' is not enabled"

    if decision.watched and not notify["notify_when_focused"]:
        return False, "pane was being watched and notify_when_focused is false"

    workspace = fields.get("workspace") or ""
    tab = fields.get("tab") or ""
    agent = fields.get("agent") or ""

    if notify["include_workspaces"] and not matches(notify["include_workspaces"], workspace):
        return False, f"workspace '{workspace}' is not in include_workspaces"
    if matches(notify["exclude_workspaces"], workspace):
        return False, f"workspace '{workspace}' is in exclude_workspaces"
    if notify["include_tabs"] and not matches(notify["include_tabs"], tab):
        return False, f"tab '{tab}' is not in include_tabs"
    if matches(notify["exclude_tabs"], tab):
        return False, f"tab '{tab}' is in exclude_tabs"
    if notify["include_agents"] and not matches(notify["include_agents"], agent):
        return False, f"agent '{agent}' is not in include_agents"
    if matches(notify["exclude_agents"], agent):
        return False, f"agent '{agent}' is in exclude_agents"

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
