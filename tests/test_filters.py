from datetime import datetime

from herdr_webhook_notify import config as config_mod
from herdr_webhook_notify import events, filters


def make_config(tmp_path, body: str):
    (tmp_path / "config.toml").write_text(body, encoding="utf-8")
    return config_mod.load(str(tmp_path / "config.toml"))


BASE = """
[providers.generic]
enabled = true
url = "http://127.0.0.1:1/hook"
"""


def decision(kind="done", watched=False):
    return events.Decision(kind, kind, watched)


def fields(**overrides):
    data = {"workspace": "w1", "tab": "1", "agent": "codex", "duration_seconds": 30}
    data.update(overrides)
    return data


def test_event_kind_filter(tmp_path):
    cfg = make_config(tmp_path, BASE + 'events = ["blocked"]\n[notify]\nevents = ["blocked"]\n')
    allowed, reason = filters.evaluate(cfg, decision("done"), fields(), {}, 0, datetime(2026, 1, 1))
    assert not allowed and "not enabled" in reason
    allowed, _ = filters.evaluate(cfg, decision("blocked"), fields(), {}, 0, datetime(2026, 1, 1))
    assert allowed


def test_watched_pane_can_be_ignored(tmp_path):
    cfg = make_config(tmp_path, BASE + "[notify]\nnotify_when_focused = false\n")
    allowed, reason = filters.evaluate(cfg, decision("done", watched=True), fields(), {}, 0, datetime(2026, 1, 1))
    assert not allowed and "watched" in reason
    allowed, _ = filters.evaluate(cfg, decision("done", watched=False), fields(), {}, 0, datetime(2026, 1, 1))
    assert allowed


def test_workspace_include_and_exclude(tmp_path):
    cfg = make_config(tmp_path, BASE + '[notify]\ninclude_workspaces = ["external-*"]\n')
    allowed, _ = filters.evaluate(cfg, decision(), fields(workspace="external-fuzzer"), {}, 0, datetime(2026, 1, 1))
    assert allowed
    allowed, reason = filters.evaluate(cfg, decision(), fields(workspace="scratch"), {}, 0, datetime(2026, 1, 1))
    assert not allowed and "include_workspaces" in reason

    cfg = make_config(tmp_path, BASE + '[notify]\nexclude_workspaces = ["scratch*"]\n')
    allowed, reason = filters.evaluate(cfg, decision(), fields(workspace="scratch-pad"), {}, 0, datetime(2026, 1, 1))
    assert not allowed and "exclude_workspaces" in reason


def test_agent_include_filter(tmp_path):
    cfg = make_config(tmp_path, BASE + '[notify]\ninclude_agents = ["codex"]\n')
    allowed, _ = filters.evaluate(cfg, decision(), fields(agent="codex"), {}, 0, datetime(2026, 1, 1))
    assert allowed
    allowed, reason = filters.evaluate(cfg, decision(), fields(agent="claude"), {}, 0, datetime(2026, 1, 1))
    assert not allowed and "include_agents" in reason


def test_quiet_hours_overnight(tmp_path):
    cfg = make_config(tmp_path, BASE + '[notify]\nquiet_hours = ["22:00-08:00"]\n')
    night = datetime(2026, 1, 1, 23, 30)
    morning = datetime(2026, 1, 1, 7, 59)
    noon = datetime(2026, 1, 1, 12, 0)
    assert not filters.evaluate(cfg, decision(), fields(), {}, 0, night)[0]
    assert not filters.evaluate(cfg, decision(), fields(), {}, 0, morning)[0]
    assert filters.evaluate(cfg, decision(), fields(), {}, 0, noon)[0]


def test_quiet_hours_blocked_is_exempt_by_default(tmp_path):
    cfg = make_config(tmp_path, BASE + '[notify]\nquiet_hours = ["22:00-08:00"]\n')
    night = datetime(2026, 1, 1, 23, 30)
    assert filters.evaluate(cfg, decision("blocked"), fields(), {}, 0, night)[0]


def test_min_turn_seconds(tmp_path):
    cfg = make_config(tmp_path, BASE + "[notify]\nmin_turn_seconds = 60\n")
    allowed, reason = filters.evaluate(cfg, decision(), fields(duration_seconds=10), {}, 0, datetime(2026, 1, 1))
    assert not allowed and "min_turn_seconds" in reason
    assert filters.evaluate(cfg, decision(), fields(duration_seconds=90), {}, 0, datetime(2026, 1, 1))[0]


def test_cooldown_uses_previous_notification(tmp_path):
    cfg = make_config(tmp_path, BASE + "[notify]\ncooldown_seconds = 30\n")
    entry = {"last_notified": {"done": 100.0}}
    allowed, reason = filters.evaluate(cfg, decision(), fields(), entry, 110.0, datetime(2026, 1, 1))
    assert not allowed and "cooldown" in reason
    assert filters.evaluate(cfg, decision(), fields(), entry, 200.0, datetime(2026, 1, 1))[0]
