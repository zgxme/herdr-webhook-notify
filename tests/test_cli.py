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
