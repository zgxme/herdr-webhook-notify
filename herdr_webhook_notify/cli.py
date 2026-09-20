"""Command dispatch: event hooks plus the init/test/status/toggle actions."""

from __future__ import annotations

import base64
import json
import os
import socket
import sys
import time
from datetime import datetime

from . import (
    __version__,
    events,
    filters,
    herdr,
    http,
    i18n,
    markup,
    providers,
    render,
)
from . import (
    config as config_mod,
)
from . import (
    state as state_mod,
)
from .providers import base

USAGE = f"""herdr-webhook-notify {__version__}

Usage:
  python3 run.py notify            run as a Herdr event hook (default)
  python3 run.py test [provider]   send a test notification
  python3 run.py init [--force]    write a starter config.toml
  python3 run.py status            show the effective configuration
  python3 run.py toggle on|off     silence or resume notifications
"""


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def out(message: str = "") -> None:
    print(message, flush=True)


def first_str(*values) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def read_json_env(name: str) -> dict:
    raw = os.environ.get(name, "")
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        log(f"invalid {name}: {exc}")
        return {}
    return payload if isinstance(payload, dict) else {}


def main(argv=None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    command = args[0].lower() if args else ""
    if not command:
        action = os.environ.get("HERDR_PLUGIN_ACTION_ID", "")
        if action:
            command = action.rsplit(".", 1)[-1].lower()
        elif os.environ.get("HERDR_PLUGIN_EVENT"):
            command = "notify"
        else:
            command = "help"

    handlers = {
        "notify": cmd_notify,
        "test": cmd_test,
        "init": cmd_init,
        "status": cmd_status,
        "toggle": cmd_toggle,
        "help": cmd_help,
        "--help": cmd_help,
        "-h": cmd_help,
        "version": cmd_version,
        "--version": cmd_version,
    }
    handler = handlers.get(command)
    if handler is None:
        log(f"unknown command: {command}")
        out(USAGE)
        return 2

    try:
        return handler(args[1:])
    except config_mod.ConfigError as exc:
        log(f"config error: {exc}")
        return 0 if command == "notify" else 1
    except Exception as exc:  # a broken hook must never break Herdr
        log(f"unexpected error: {exc}")
        return 0 if command == "notify" else 1


def cmd_help(_args) -> int:
    out(USAGE)
    return 0


def cmd_version(_args) -> int:
    out(__version__)
    return 0


# --------------------------------------------------------------------- notify


def collect_fields(pane_id: str, data: dict, context: dict, entry: dict, started_at, now: float) -> dict:
    info = herdr.pane(pane_id) if pane_id else {}
    # Context pane fields describe this pane only when the ids match.
    context_pane = context if first_str(context.get("focused_pane_id")) == pane_id else {}

    workspace_id = first_str(
        data.get("workspace_id"),
        context.get("workspace_id"),
        info.get("workspace_id"),
        entry.get("workspace_id"),
    )
    tab_id = first_str(context.get("tab_id"), info.get("tab_id"), entry.get("tab_id"))
    cwd = first_str(
        context_pane.get("focused_pane_cwd"),
        context.get("workspace_cwd"),
        info.get("foreground_cwd"),
        info.get("cwd"),
        entry.get("cwd"),
    )
    duration = None
    if isinstance(started_at, (int, float)) and now >= started_at:
        duration = now - started_at

    return {
        "session": first_str(os.environ.get("HERDR_SESSION"), entry.get("session")) or "default",
        "workspace": first_str(
            context.get("workspace_label"),
            data.get("workspace_label"),
            herdr.workspace_label(workspace_id),
            workspace_id,
            entry.get("workspace"),
        ),
        "tab": first_str(
            context.get("tab_label"),
            herdr.tab_label(tab_id),
            tab_id,
            entry.get("tab"),
        ),
        "task": first_str(
            info.get("terminal_title_stripped"),
            info.get("terminal_title"),
            data.get("title"),
            entry.get("task"),
            pane_id,
        ),
        "agent": first_str(
            context_pane.get("focused_pane_agent"),
            data.get("display_agent"),
            data.get("agent"),
            info.get("agent"),
            entry.get("agent"),
        ),
        "pane_id": pane_id,
        "cwd": cwd,
        "branch": herdr.git_branch(cwd),
        "duration": render.format_duration(duration),
        "duration_seconds": duration,
        "host": socket.gethostname(),
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "workspace_id": workspace_id,
        "tab_id": tab_id,
    }


def build_message(cfg, kind: str, status: str, fields: dict, language: str, timestamp: int, module):
    values = dict(fields)
    values["kind"] = kind
    values["status"] = status
    values["status_label"] = i18n.status_label(language, kind, cfg.messages)

    flavor = module.flavor(cfg.provider_options(module.NAME)) if hasattr(module, "flavor") else module.FLAVOR
    title_template = cfg.message.get("title") or i18n.translate(language, "title", cfg.messages)
    body_template = cfg.message.get("body") or i18n.translate(language, "body", cfg.messages)
    title = render.drop_empty_lines(markup.convert(render.render(title_template, values), flavor))
    body = render.drop_empty_lines(markup.convert(render.render(body_template, values), flavor))
    return base.Message(
        kind=kind,
        status=status,
        title=title,
        body=body,
        fields=values,
        timestamp=timestamp,
    )


def deliver(cfg, kind: str, status: str, fields: dict, timestamp: int, only=None, ignore_events=False):
    """Send the notification to every enabled provider. Returns result tuples."""
    results = []
    for name in cfg.enabled:
        if only and name not in only:
            continue
        options = cfg.provider_options(name)
        module = providers.get(name)
        provider_events = options.get("events")
        if not ignore_events and provider_events and kind not in provider_events:
            results.append((name, True, None, "skipped: kind not enabled for this provider"))
            continue

        language = i18n.normalize(options.get("language") or cfg.language)
        message = build_message(cfg, kind, status, fields, language, timestamp, module)
        try:
            delivery = module.build(options, message)
        except Exception as exc:
            results.append((name, False, None, f"build failed: {exc}"))
            continue

        response = http.send(
            delivery.url,
            delivery.body,
            delivery.headers,
            timeout=float(cfg.http.get("timeout_seconds", 5)),
            retries=int(cfg.http.get("retries", 1)),
        )
        if response.ok:
            results.append((name, True, response.status, response.body[:200]))
        else:
            results.append((name, False, response.status, response.error or response.body))
    return results


def flush_pending(cfg, state) -> int:
    items = state.pending_items()
    if not items:
        return 0
    remaining = []
    sent = 0
    for item in items:
        attempts = int(item.get("attempts") or 0)
        if attempts >= state_mod.MAX_ATTEMPTS:
            log(f"dropping queued notification for {item.get('provider')}: too many attempts")
            continue
        try:
            body = base64.b64decode(item.get("body") or "")
        except (ValueError, TypeError):
            continue
        response = http.send(
            item.get("url", ""),
            body,
            item.get("headers") or {},
            timeout=float(cfg.http.get("timeout_seconds", 5)),
            retries=int(cfg.http.get("retries", 1)),
        )
        if response.ok:
            sent += 1
            continue
        item["attempts"] = attempts + 1
        item["last_error"] = response.error or response.body
        remaining.append(item)
    state.replace_pending(remaining)
    return sent


def cmd_notify(_args) -> int:
    state = state_mod.State()
    cfg = config_mod.load()

    if state.is_disabled():
        log("notifications are silenced, run 'toggle on' to resume")
        return 0
    if not cfg.enabled:
        for warning in cfg.warnings:
            log(warning)
        return 0

    # Anything that failed earlier gets another chance before new work.
    flushed = flush_pending(cfg, state)
    if flushed:
        log(f"flushed {flushed} queued notification(s)")

    event = read_json_env("HERDR_PLUGIN_EVENT_JSON")
    context = read_json_env("HERDR_PLUGIN_CONTEXT_JSON")
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    event_name = first_str(
        os.environ.get("HERDR_PLUGIN_EVENT"),
        event.get("event") if isinstance(event.get("event"), str) else "",
    )

    pane_id = first_str(data.get("pane_id"), os.environ.get("HERDR_PANE_ID"))
    if not pane_id:
        log("event carries no pane id, nothing to do")
        return 0

    entry = state.pane(pane_id)
    previous_status = first_str(entry.get("status")).lower()
    decision = events.classify(event_name, data, previous_status)
    now = time.time()

    raw_status = first_str(data.get("agent_status")).lower()
    if events.status_event(event_name, data):
        started_at = entry.get("started_at")
        if raw_status == "working" and previous_status != "working":
            started_at = now
        state.update_pane(
            pane_id,
            status=raw_status,
            started_at=started_at,
            status_seen_at=now,
        )
    elif events.exit_event(event_name, data):
        state.forget_pane(pane_id)

    fields = collect_fields(pane_id, data, context, entry, entry.get("started_at"), now)
    if events.status_event(event_name, data):
        state.update_pane(
            pane_id,
            agent=fields["agent"],
            task=fields["task"],
            workspace=fields["workspace"],
            workspace_id=fields["workspace_id"],
            tab=fields["tab"],
            tab_id=fields["tab_id"],
            cwd=fields["cwd"],
            session=fields["session"],
        )
    state.save()

    if decision is None:
        return 0

    allowed, reason = filters.evaluate(cfg, decision, fields, entry, now, datetime.now())
    if not allowed:
        log(f"skip notification: {reason}")
        return 0

    results = deliver(cfg, decision.kind, decision.status, fields, int(now))
    sent = 0
    for name, ok, status_code, detail in results:
        if ok:
            sent += 1
            log(f"{name}: delivered ({status_code})")
        else:
            log(f"{name}: failed ({detail})")
            if detail.startswith("build failed"):
                continue
            options = cfg.provider_options(name)
            module = providers.get(name)
            try:
                message = build_message(
                    cfg,
                    decision.kind,
                    decision.status,
                    fields,
                    i18n.normalize(options.get("language") or cfg.language),
                    int(now),
                    module,
                )
                state.queue(name, module.build(options, message), detail)
            except Exception:  # queueing is best effort
                pass

    if sent:
        state.mark_notified(pane_id, decision.kind, now)
    state.save()

    if not sent and results:
        log("no provider accepted the notification")
    return 0


# ----------------------------------------------------------------------- test


def sample_fields() -> dict:
    context = read_json_env("HERDR_PLUGIN_CONTEXT_JSON")
    return {
        "session": first_str(os.environ.get("HERDR_SESSION")) or "default",
        "workspace": first_str(context.get("workspace_label"), context.get("workspace_id")) or "my-workspace",
        "tab": first_str(context.get("tab_label"), context.get("tab_id")) or "1",
        "task": "herdr-webhook-notify test notification",
        "agent": first_str(context.get("focused_pane_agent")) or "codex",
        "pane_id": first_str(os.environ.get("HERDR_PANE_ID")) or "w1:p1",
        "cwd": os.getcwd(),
        "branch": herdr.git_branch(os.getcwd()),
        "duration": "12s",
        "duration_seconds": 12,
        "host": socket.gethostname(),
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "workspace_id": first_str(context.get("workspace_id")),
        "tab_id": first_str(context.get("tab_id")),
    }


def cmd_test(args) -> int:
    cfg = config_mod.load()
    if not cfg.enabled:
        out("No provider is enabled yet.")
        out(f"Config file: {config_mod.resolve_path()}")
        out("Run 'init' to write a starter config, then set enabled = true.")
        return 1

    only = None
    for arg in args:
        if arg.startswith("-"):
            continue
        only = {arg}
        if providers.get(arg) is None:
            out(f"Unknown provider '{arg}'. Available: {', '.join(providers.names())}")
            return 2

    fields = sample_fields()
    results = deliver(cfg, "test", "test", fields, int(time.time()), only=only, ignore_events=True)
    failures = 0
    for name, ok, status_code, detail in results:
        if ok:
            out(f"OK   {name} (HTTP {status_code})")
        else:
            failures += 1
            out(f"FAIL {name}: {detail}")
    return 1 if failures else 0


# ----------------------------------------------------------------------- init


def cmd_init(args) -> int:
    force = "--force" in args
    target = config_mod.resolve_path(for_write=True)
    example = config_mod.plugin_root() / "examples" / "config.toml"
    if target.exists() and not force:
        out(f"Config already exists: {target}")
        out("Re-run with --force to overwrite it.")
        return 1
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    except OSError as exc:
        out(f"Cannot write {target}: {exc}")
        return 1

    out(f"Wrote {target}")
    out("")
    out("Next steps:")
    out("  1. open the file and set enabled = true on the provider you use")
    out("  2. put secrets in an .env file next to it, e.g. FEISHU_WEBHOOK=...")
    out("  3. verify with: herdr plugin action invoke herdr-webhook-notify.test")
    return 0


# --------------------------------------------------------------------- status


def cmd_status(_args) -> int:
    cfg = config_mod.load()
    state = state_mod.State()
    path = cfg.path

    out(f"herdr-webhook-notify {__version__}")
    out(f"config      : {path if path else 'built-in defaults (no config.toml found)'}")
    out(f"state       : {state.path}")
    out(f"language    : {cfg.language} (available: {', '.join(i18n.available())})")
    out(f"silenced    : {state.is_disabled()}")
    notify = cfg.notify
    out(f"events      : {', '.join(notify['events'])}")
    out(f"focused     : {'notify' if notify['notify_when_focused'] else 'skip'} when you watch the pane")
    out(f"min turn    : {notify['min_turn_seconds']:g}s   cooldown: {notify['cooldown_seconds']:g}s")
    if notify["include_workspaces"]:
        out(f"include ws  : {', '.join(notify['include_workspaces'])}")
    if notify["exclude_workspaces"]:
        out(f"exclude ws  : {', '.join(notify['exclude_workspaces'])}")
    if notify["include_agents"]:
        out(f"include ag  : {', '.join(notify['include_agents'])}")
    if notify["exclude_agents"]:
        out(f"exclude ag  : {', '.join(notify['exclude_agents'])}")
    out(f"quiet hours : {', '.join(str(item) for item in notify['quiet_hours_exempt'])} exempt")

    out("")
    if cfg.enabled:
        out("providers:")
        for name in cfg.enabled:
            options = cfg.provider_options(name)
            module = providers.get(name)
            target = first_str(options.get("webhook_url"), options.get("url"), options.get("topic"), options.get("chat_id"))
            detail = http.redact(target) if target.startswith("http") else target
            language = i18n.normalize(options.get("language") or cfg.language)
            out(f"  - {name} ({module.TITLE}) language={language} {detail}")
    else:
        out("providers: none enabled")

    pending = state.pending_items()
    out("")
    out(f"queued      : {len(pending)}")
    for item in pending[-3:]:
        out(f"  - {item.get('provider')} attempts={item.get('attempts')} error={item.get('last_error')}")

    for warning in cfg.warnings:
        out(f"warning     : {warning}")
    return 0


# --------------------------------------------------------------------- toggle


def cmd_toggle(args) -> int:
    state = state_mod.State()
    action = args[0].lower() if args else ""
    if action in ("on", "resume", "enable"):
        state.set_disabled(False)
        state.save()
        out("notifications enabled")
        return 0
    if action in ("off", "mute", "disable"):
        state.set_disabled(True)
        state.save()
        out("notifications silenced (run 'toggle on' to resume)")
        return 0
    out(f"notifications are {'silenced' if state.is_disabled() else 'enabled'}")
    out("usage: toggle on|off")
    return 0
