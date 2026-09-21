"""Small JSON state file: per-pane status, cooldowns and a pending queue."""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

STATE_VERSION = 1
PANE_KEEP_SECONDS = 7 * 24 * 3600
MAX_PENDING = 20
MAX_ATTEMPTS = 3


def default_path() -> Path:
    state_dir = os.environ.get("HERDR_PLUGIN_STATE_DIR")
    if state_dir:
        return Path(state_dir) / "state.json"
    return Path(__file__).resolve().parent.parent / "state.json"


class State:
    def __init__(self, path: Path = None):
        self.path = Path(path) if path else default_path()
        self.data = {"version": STATE_VERSION, "panes": {}, "pending": [], "disabled": False}
        self.load()

    # ---------------------------------------------------------------- io
    def load(self) -> None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(payload, dict):
            return
        panes = payload.get("panes")
        pending = payload.get("pending")
        self.data = {
            "version": STATE_VERSION,
            "panes": panes if isinstance(panes, dict) else {},
            "pending": pending if isinstance(pending, list) else [],
            "disabled": bool(payload.get("disabled", False)),
        }

    def save(self) -> None:
        self._prune_panes()
        self.data["pending"] = self.data["pending"][-MAX_PENDING:]
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_name(self.path.name + ".tmp")
            temp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(self.path)
        except OSError:
            pass

    def _prune_panes(self) -> None:
        now = time.time()
        kept = {}
        for pane_id, entry in self.data["panes"].items():
            if not isinstance(entry, dict):
                continue
            updated = entry.get("updated")
            if isinstance(updated, (int, float)) and now - updated > PANE_KEEP_SECONDS:
                continue
            kept[pane_id] = entry
        self.data["panes"] = kept

    # ------------------------------------------------------------- panes
    def pane(self, pane_id: str) -> dict:
        entry = self.data["panes"].get(pane_id)
        return entry if isinstance(entry, dict) else {}

    def update_pane(self, pane_id: str, **fields) -> dict:
        entry = dict(self.pane(pane_id))
        entry.update({key: value for key, value in fields.items() if value is not None})
        entry["updated"] = time.time()
        self.data["panes"][pane_id] = entry
        return entry

    def forget_pane(self, pane_id: str) -> None:
        self.data["panes"].pop(pane_id, None)

    def mark_notified(self, pane_id: str, kind: str, when: float) -> None:
        entry = dict(self.pane(pane_id))
        last = dict(entry.get("last_notified") or {})
        last[kind] = when
        entry["last_notified"] = last
        entry["updated"] = when
        self.data["panes"][pane_id] = entry

    # ----------------------------------------------------------- pending
    def queue(self, provider: str, delivery, error: str) -> None:
        self.data["pending"].append(
            {
                "provider": provider,
                "url": delivery.url,
                "method": getattr(delivery, "method", "POST"),
                "headers": delivery.headers,
                "body": base64.b64encode(delivery.body).decode("ascii"),
                "attempts": (self.pending_attempts(provider, delivery.url) + 1),
                "last_error": error,
                "created": time.time(),
            }
        )

    def pending_attempts(self, provider: str, url: str) -> int:
        for item in reversed(self.data["pending"]):
            if item.get("provider") == provider and item.get("url") == url:
                return int(item.get("attempts") or 0)
        return 0

    def pending_items(self) -> list:
        return list(self.data["pending"])

    def replace_pending(self, items) -> None:
        self.data["pending"] = list(items)

    # ---------------------------------------------------------- disabled
    def is_disabled(self) -> bool:
        return bool(self.data.get("disabled"))

    def set_disabled(self, value: bool) -> None:
        self.data["disabled"] = bool(value)
