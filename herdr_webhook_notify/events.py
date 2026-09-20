"""Turn Herdr events into notification decisions."""

from __future__ import annotations

from dataclasses import dataclass

ACTIVE_STATES = {"working", "blocked"}


@dataclass
class Decision:
    kind: str
    status: str
    watched: bool


def status_event(event_name: str, data: dict) -> bool:
    return data.get("type") == "pane_agent_status_changed" or "agent_status_changed" in event_name


def exit_event(event_name: str, data: dict) -> bool:
    data_type = data.get("type")
    if data_type in ("pane_exited", "pane_closed"):
        return True
    return "exited" in event_name or event_name.endswith("pane.closed")


def classify(event_name: str, data: dict, previous_status: str) -> Decision:
    """Return the notification to send, or None when the event is noise.

    Herdr reports a finished turn as `done` only while the completion is
    unseen. Watching the pane makes it arrive as `idle`, which is why the
    previous status is required to recognise a completion.
    """
    if status_event(event_name, data):
        status = str(data.get("agent_status") or "").strip().lower()
        if status == "blocked":
            return Decision("blocked", status, watched=False)
        if status == "done":
            return Decision("done", status, watched=False)
        if status == "idle" and previous_status in ACTIVE_STATES:
            return Decision("done", status, watched=True)
        if status == "unknown" and previous_status in ACTIVE_STATES:
            return Decision("unknown", status, watched=False)
        return None

    if exit_event(event_name, data) and previous_status:
        return Decision("exited", "exited", watched=False)

    return None
