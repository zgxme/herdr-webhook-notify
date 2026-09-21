"""Read-only helpers around the Herdr CLI."""

from __future__ import annotations

import json
import os
import subprocess

CACHE = {}


def binary() -> str:
    return os.environ.get("HERDR_BIN_PATH") or "herdr"


def cli_json(args, fresh: bool = False) -> dict:
    key = tuple(args)
    if not fresh and key in CACHE:
        return CACHE[key]
    result = {}
    try:
        completed = subprocess.run(
            [binary()] + list(args),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            result = json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        result = {}
    CACHE[key] = result
    return result


def _items(payload: dict, key: str) -> list:
    result = payload.get("result")
    if isinstance(result, dict):
        items = result.get(key)
        if isinstance(items, list):
            return items
    return []


def panes() -> list:
    return _items(cli_json(["pane", "list"]), "panes")


def workspaces() -> list:
    return _items(cli_json(["workspace", "list"]), "workspaces")


def tabs() -> list:
    return _items(cli_json(["tab", "list"]), "tabs")


def pane(pane_id: str) -> dict:
    for item in panes():
        if isinstance(item, dict) and item.get("pane_id") == pane_id:
            return item
    return {}


def agent_status(pane_id: str):
    """Read the current agent status of one pane.

    Returns ``None`` when Herdr cannot be queried, which callers should treat as
    "unknown" instead of "not blocked". An empty string means the pane is gone,
    which is different: a pane that no longer exists cannot be waiting.
    """
    payload = cli_json(["pane", "list"], fresh=True)
    if not payload:
        return None
    for item in _items(payload, "panes"):
        if isinstance(item, dict) and item.get("pane_id") == pane_id:
            status = item.get("agent_status")
            return status.strip().lower() if isinstance(status, str) else None
    return ""


def workspace_label(workspace_id: str) -> str:
    for item in workspaces():
        if isinstance(item, dict) and item.get("workspace_id") == workspace_id:
            label = item.get("label")
            if isinstance(label, str) and label.strip():
                return label.strip()
    return ""


def tab_label(tab_id: str) -> str:
    for item in tabs():
        if isinstance(item, dict) and item.get("tab_id") == tab_id:
            label = item.get("label")
            if isinstance(label, str) and label.strip():
                return label.strip()
    return ""


def git_branch(cwd: str) -> str:
    if not cwd:
        return ""
    try:
        completed = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if completed.returncode != 0:
        return ""
    branch = completed.stdout.strip()
    return "" if branch in ("HEAD", "") else branch
