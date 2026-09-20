from herdr_webhook_notify import events


def test_completion_while_watched_counts_as_done():
    decision = events.classify("pane.agent_status_changed", {"agent_status": "idle"}, "working")
    assert decision == events.Decision("done", "idle", watched=True)


def test_background_completion():
    decision = events.classify("pane.agent_status_changed", {"agent_status": "done"}, "working")
    assert decision.kind == "done"
    assert decision.watched is False


def test_blocked_is_always_reported():
    decision = events.classify("pane.agent_status_changed", {"agent_status": "blocked"}, "working")
    assert decision.kind == "blocked"


def test_startup_idle_is_noise():
    assert events.classify("pane.agent_status_changed", {"agent_status": "idle"}, "") is None


def test_working_is_noise():
    assert events.classify("pane.agent_status_changed", {"agent_status": "working"}, "") is None


def test_unknown_after_work_is_reported():
    decision = events.classify("pane.agent_status_changed", {"agent_status": "unknown"}, "working")
    assert decision.kind == "unknown"


def test_exit_after_work_is_reported():
    decision = events.classify("pane.exited", {"type": "pane_exited"}, "working")
    assert decision.kind == "exited"


def test_exit_without_agent_history_is_noise():
    assert events.classify("pane.exited", {"type": "pane_exited"}, "") is None


def test_pane_closed_counts_as_exit():
    decision = events.classify("pane.closed", {"type": "pane_closed"}, "working")
    assert decision.kind == "exited"
