import json
from pathlib import Path

from herdr_webhook_notify import cli
from herdr_webhook_notify import state as state_mod


def webhook_url(server) -> str:
    return f"http://127.0.0.1:{server.server_port}/hook/test"


FEISHU_CONFIG = """
language = "{language}"

[notify]
{notify}

[http]
retries = 0

[providers.feishu]
enabled = true
webhook_url = "{url}"
"""


def write_config(config_dir, url, language="en", notify=""):
    text = FEISHU_CONFIG.format(language=language, url=url, notify=notify)
    (Path(config_dir) / "config.toml").write_text(text, encoding="utf-8")


def send_event(monkeypatch, event_name, data, context=None):
    monkeypatch.setenv("HERDR_PLUGIN_EVENT", event_name)
    monkeypatch.setenv("HERDR_PLUGIN_EVENT_JSON", json.dumps({"event": event_name, "data": data}))
    if context is None:
        context = {
            "workspace_id": "wD",
            "workspace_label": "external-fuzzer",
            "tab_id": "wD:t1",
            "tab_label": "2",
            "focused_pane_id": "wD:p1",
            "focused_pane_agent": "codex",
            "focused_pane_cwd": "/tmp/work",
        }
    monkeypatch.setenv("HERDR_PLUGIN_CONTEXT_JSON", json.dumps(context))
    return cli.main(["notify"])


def status_event(status):
    return {"type": "pane_agent_status_changed", "pane_id": "wD:p1", "workspace_id": "wD", "agent_status": status}


def test_watched_completion_is_reported(isolated_env, webhook_server, monkeypatch):
    write_config(isolated_env["config_dir"], webhook_url(webhook_server))
    send_event(monkeypatch, "pane.agent_status_changed", status_event("working"))
    assert webhook_server.requests == []

    send_event(monkeypatch, "pane.agent_status_changed", status_event("idle"))
    assert len(webhook_server.requests) == 1
    card = json.loads(webhook_server.requests[0]["body"])["card"]
    assert card["header"]["title"]["content"].startswith("Herdr Task finished")
    assert "**Workspace**: external-fuzzer" in card["elements"][0]["content"]
    assert "**Task**: wD:p1" in card["elements"][0]["content"]


def test_background_completion_is_reported(isolated_env, webhook_server, monkeypatch):
    write_config(isolated_env["config_dir"], webhook_url(webhook_server))
    send_event(monkeypatch, "pane.agent_status_changed", status_event("working"))
    send_event(monkeypatch, "pane.agent_status_changed", status_event("done"))
    assert len(webhook_server.requests) == 1
    assert json.loads(webhook_server.requests[0]["body"])["card"]["header"]["template"] == "green"


def test_startup_idle_is_ignored(isolated_env, webhook_server, monkeypatch):
    write_config(isolated_env["config_dir"], webhook_url(webhook_server))
    send_event(monkeypatch, "pane.agent_status_changed", status_event("idle"))
    assert webhook_server.requests == []


def test_blocked_notification(isolated_env, webhook_server, monkeypatch):
    write_config(isolated_env["config_dir"], webhook_url(webhook_server))
    send_event(monkeypatch, "pane.agent_status_changed", status_event("blocked"))
    assert len(webhook_server.requests) == 1
    assert json.loads(webhook_server.requests[0]["body"])["card"]["header"]["template"] == "orange"


def test_unknown_after_work_is_reported(isolated_env, webhook_server, monkeypatch):
    write_config(isolated_env["config_dir"], webhook_url(webhook_server))
    send_event(monkeypatch, "pane.agent_status_changed", status_event("working"))
    send_event(monkeypatch, "pane.agent_status_changed", status_event("unknown"))
    assert len(webhook_server.requests) == 1
    assert json.loads(webhook_server.requests[0]["body"])["card"]["header"]["template"] == "red"


def test_pane_exit_after_work_is_reported(isolated_env, webhook_server, monkeypatch):
    write_config(isolated_env["config_dir"], webhook_url(webhook_server))
    send_event(monkeypatch, "pane.agent_status_changed", status_event("working"))
    send_event(
        monkeypatch,
        "pane.exited",
        {"type": "pane_exited", "pane_id": "wD:p1", "workspace_id": "wD"},
    )
    assert len(webhook_server.requests) == 1
    assert "Session process exited" in webhook_server.requests[0]["body"].decode()


def test_chinese_language(isolated_env, webhook_server, monkeypatch):
    write_config(isolated_env["config_dir"], webhook_url(webhook_server), language="zh-CN")
    send_event(monkeypatch, "pane.agent_status_changed", status_event("done"))
    body = webhook_server.requests[0]["body"].decode("utf-8")
    assert "任务完成" in body
    assert "external-fuzzer" in body


def test_workspace_exclude_skips(isolated_env, webhook_server, monkeypatch):
    write_config(
        isolated_env["config_dir"],
        webhook_url(webhook_server),
        notify='exclude_workspaces = ["external-*"]',
    )
    send_event(monkeypatch, "pane.agent_status_changed", status_event("done"))
    assert webhook_server.requests == []


def test_cooldown_prevents_duplicates(isolated_env, webhook_server, monkeypatch):
    write_config(
        isolated_env["config_dir"],
        webhook_url(webhook_server),
        notify="cooldown_seconds = 600",
    )
    send_event(monkeypatch, "pane.agent_status_changed", status_event("done"))
    send_event(monkeypatch, "pane.agent_status_changed", status_event("done"))
    assert len(webhook_server.requests) == 1


def test_provider_event_override(isolated_env, webhook_server, monkeypatch):
    text = f"""
[http]
retries = 0

[providers.feishu]
enabled = true
webhook_url = "{webhook_url(webhook_server)}"
events = ["blocked"]
"""
    (Path(isolated_env["config_dir"]) / "config.toml").write_text(text, encoding="utf-8")
    send_event(monkeypatch, "pane.agent_status_changed", status_event("done"))
    assert webhook_server.requests == []
    send_event(monkeypatch, "pane.agent_status_changed", status_event("blocked"))
    assert len(webhook_server.requests) == 1


def test_failed_delivery_is_queued_and_retried(isolated_env, webhook_server, monkeypatch):
    write_config(isolated_env["config_dir"], webhook_url(webhook_server))
    webhook_server.next_status = 500
    send_event(monkeypatch, "pane.agent_status_changed", status_event("done"))
    assert len(webhook_server.requests) == 1

    state = state_mod.State()
    assert len(state.pending_items()) == 1
    assert state.pending_items()[0]["attempts"] == 1

    webhook_server.next_status = 200
    send_event(monkeypatch, "pane.agent_status_changed", status_event("working"))
    state = state_mod.State()
    assert state.pending_items() == []


def test_toggle_silences_notifications(isolated_env, webhook_server, monkeypatch):
    write_config(isolated_env["config_dir"], webhook_url(webhook_server))
    assert cli.main(["toggle", "off"]) == 0
    send_event(monkeypatch, "pane.agent_status_changed", status_event("done"))
    assert webhook_server.requests == []
    assert cli.main(["toggle", "on"]) == 0
    send_event(monkeypatch, "pane.agent_status_changed", status_event("done"))
    assert len(webhook_server.requests) == 1


def test_init_writes_config(isolated_env, capsys):
    assert cli.main(["init"]) == 0
    target = Path(isolated_env["config_dir"]) / "config.toml"
    assert target.is_file()
    assert cli.main(["init"]) == 1  # refuses to overwrite
    assert cli.main(["init", "--force"]) == 0


def test_status_runs_without_config(isolated_env, capsys):
    assert cli.main(["status"]) == 0
    output = capsys.readouterr().out
    assert "herdr-webhook-notify" in output
    assert "language    : en" in output


def test_test_command_reports_failure_without_providers(isolated_env, capsys):
    assert cli.main(["test"]) == 1
    assert "No provider is enabled" in capsys.readouterr().out


def test_test_command_sends_sample(isolated_env, webhook_server, capsys):
    write_config(isolated_env["config_dir"], webhook_url(webhook_server))
    assert cli.main(["test"]) == 0
    assert "OK   feishu" in capsys.readouterr().out
    assert len(webhook_server.requests) == 1


def write_generic_config(config_dir, url, method="POST"):
    text = f"""
[http]
retries = 0

[providers.generic]
enabled = true
url = "{url}"
method = "{method}"
"""
    (Path(config_dir) / "config.toml").write_text(text, encoding="utf-8")


def test_generic_provider_sends_with_configured_method(isolated_env, webhook_server, capsys):
    write_generic_config(isolated_env["config_dir"], webhook_url(webhook_server), method="PUT")
    assert cli.main(["test"]) == 0
    assert len(webhook_server.requests) == 1
    assert webhook_server.requests[0]["method"] == "PUT"


def test_queued_notification_replays_with_its_method(isolated_env, webhook_server, monkeypatch):
    write_generic_config(isolated_env["config_dir"], webhook_url(webhook_server), method="PATCH")
    webhook_server.next_status = 500
    send_event(monkeypatch, "pane.agent_status_changed", status_event("done"))
    assert len(webhook_server.requests) == 1

    state = state_mod.State()
    assert state.pending_items()[0]["method"] == "PATCH"

    webhook_server.next_status = 200
    send_event(monkeypatch, "pane.agent_status_changed", status_event("working"))
    assert len(webhook_server.requests) == 2
    assert webhook_server.requests[1]["method"] == "PATCH"
    assert state_mod.State().pending_items() == []


def test_worktree_placeholders(isolated_env, webhook_server, monkeypatch):
    text = f"""
[http]
retries = 0

[message]
body = "{{repo}}|{{worktree}}|{{workspace}}"

[providers.feishu]
enabled = true
webhook_url = "{webhook_url(webhook_server)}"
"""
    (Path(isolated_env["config_dir"]) / "config.toml").write_text(text, encoding="utf-8")
    context = {
        "workspace_id": "wD",
        "workspace_label": "external-fuzzer",
        "tab_id": "wD:t1",
        "tab_label": "2",
        "focused_pane_id": "wD:p1",
        "focused_pane_agent": "codex",
        "focused_pane_cwd": "/tmp/work",
        "worktree": {
            "repo_key": "github.com/zgxme/herdr-webhook-notify",
            "repo_name": "herdr-webhook-notify",
            "repo_root": "/home/u/src/herdr-webhook-notify",
            "checkout_path": "/home/u/src/herdr-webhook-notify.worktrees/fix",
            "is_linked_worktree": True,
        },
    }
    send_event(monkeypatch, "pane.agent_status_changed", status_event("done"), context=context)
    body = json.loads(webhook_server.requests[0]["body"])["card"]["elements"][0]["content"]
    assert body == "herdr-webhook-notify|/home/u/src/herdr-webhook-notify.worktrees/fix|external-fuzzer"


def test_worktree_placeholders_drop_the_line_outside_a_worktree(
    isolated_env, webhook_server, monkeypatch
):
    text = f"""
[http]
retries = 0

[message]
body = "**Repo**: {{repo}}"

[providers.feishu]
enabled = true
webhook_url = "{webhook_url(webhook_server)}"
"""
    (Path(isolated_env["config_dir"]) / "config.toml").write_text(text, encoding="utf-8")
    send_event(monkeypatch, "pane.agent_status_changed", status_event("done"))
    body = json.loads(webhook_server.requests[0]["body"])["card"]["elements"][0]["content"]
    assert "Repo" not in body


def test_status_shows_quiet_hours_and_tab_filters(isolated_env, capsys):
    text = """
[notify]
quiet_hours = ["22:00-08:00"]
include_tabs = ["2"]
exclude_tabs = ["9"]
"""
    (Path(isolated_env["config_dir"]) / "config.toml").write_text(text, encoding="utf-8")
    assert cli.main(["status"]) == 0
    output = capsys.readouterr().out
    assert "quiet hours : 22:00-08:00 (exempt: blocked)" in output
    assert "include tab : 2" in output
    assert "exclude tab : 9" in output


def test_status_shows_every_effective_setting(isolated_env, webhook_server, capsys):
    text = f"""
[notify]
blocked_delay_seconds = 0

[http]
timeout_seconds = 12
retries = 3

[message]
body = "{{task}}"

[providers.feishu]
enabled = true
webhook_url = "{webhook_url(webhook_server)}"
events = ["blocked"]
"""
    (Path(isolated_env["config_dir"]) / "config.toml").write_text(text, encoding="utf-8")
    assert cli.main(["status"]) == 0
    output = capsys.readouterr().out
    assert "blocked wait: 0s" in output
    assert "http        : timeout 12s   retries 3" in output
    assert "message     : custom: body" in output
    assert "events=[blocked]" in output


def test_status_shows_built_in_defaults(isolated_env, capsys):
    assert cli.main(["status"]) == 0
    output = capsys.readouterr().out
    assert "blocked wait: 10s" in output
    assert "http        : timeout 5s   retries 1" in output
    assert "message     : built-in" in output


def test_status_reports_missing_quiet_hours(isolated_env, capsys):
    assert cli.main(["status"]) == 0
    assert "quiet hours : none (exempt: blocked)" in capsys.readouterr().out


def blocked_config(config_dir, url, extra=""):
    text = f"""
[notify]
{extra}

[http]
retries = 0

[providers.feishu]
enabled = true
webhook_url = "{url}"
"""
    (Path(config_dir) / "config.toml").write_text(text, encoding="utf-8")


def test_blocked_waits_before_notifying(isolated_env, webhook_server, monkeypatch, no_sleep):
    blocked_config(isolated_env["config_dir"], webhook_url(webhook_server), "blocked_delay_seconds = 10")
    monkeypatch.setattr(cli.herdr, "agent_status", lambda pane_id: "blocked")
    send_event(monkeypatch, "pane.agent_status_changed", status_event("blocked"))
    assert no_sleep == [10]
    assert len(webhook_server.requests) == 1


def test_blocked_is_skipped_when_the_agent_approved_itself(
    isolated_env, webhook_server, monkeypatch, no_sleep
):
    blocked_config(isolated_env["config_dir"], webhook_url(webhook_server), "blocked_delay_seconds = 10")
    monkeypatch.setattr(cli.herdr, "agent_status", lambda pane_id: "working")
    send_event(monkeypatch, "pane.agent_status_changed", status_event("blocked"))
    assert no_sleep == [10]
    assert webhook_server.requests == []


def test_blocked_is_skipped_when_the_pane_is_gone(isolated_env, webhook_server, monkeypatch):
    blocked_config(isolated_env["config_dir"], webhook_url(webhook_server), "blocked_delay_seconds = 10")
    monkeypatch.setattr(cli.herdr, "agent_status", lambda pane_id: "")
    send_event(monkeypatch, "pane.agent_status_changed", status_event("blocked"))
    assert webhook_server.requests == []


def test_blocked_notifies_when_the_status_cannot_be_read(
    isolated_env, webhook_server, monkeypatch, no_sleep
):
    blocked_config(isolated_env["config_dir"], webhook_url(webhook_server), "blocked_delay_seconds = 10")
    monkeypatch.setattr(cli.herdr, "agent_status", lambda pane_id: None)
    send_event(monkeypatch, "pane.agent_status_changed", status_event("blocked"))
    assert no_sleep == [10]
    assert len(webhook_server.requests) == 1


def test_blocked_delay_zero_notifies_immediately(isolated_env, webhook_server, monkeypatch, no_sleep):
    blocked_config(isolated_env["config_dir"], webhook_url(webhook_server), "blocked_delay_seconds = 0")
    send_event(monkeypatch, "pane.agent_status_changed", status_event("blocked"))
    assert no_sleep == []
    assert len(webhook_server.requests) == 1


def test_completion_is_not_delayed(isolated_env, webhook_server, monkeypatch, no_sleep):
    blocked_config(isolated_env["config_dir"], webhook_url(webhook_server), "blocked_delay_seconds = 10")
    send_event(monkeypatch, "pane.agent_status_changed", status_event("done"))
    assert no_sleep == []
    assert len(webhook_server.requests) == 1
