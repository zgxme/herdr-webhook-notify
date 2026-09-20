<div align="center">

# herdr-webhook-notify

[![CI](https://github.com/zgxme/herdr-webhook-notify/actions/workflows/ci.yml/badge.svg)](https://github.com/zgxme/herdr-webhook-notify/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml)
[![Platforms](https://img.shields.io/badge/platform-linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)](herdr-plugin.toml)
[![Herdr plugin](https://img.shields.io/badge/Herdr-plugin-6E56CF.svg)](https://herdr.dev/plugins/)
[![Providers](https://img.shields.io/badge/providers-11-2EB67D.svg)](#providers)

A [Herdr](https://herdr.dev) plugin that forwards agent notifications to the
webhook service you already use: Slack, Discord, Microsoft Teams, Google Chat,
Feishu, Lark, DingTalk, WeCom, Telegram, ntfy, or any custom HTTP endpoint.

[中文说明](README.zh-CN.md) | [Provider guides](docs/providers.md) | [Contributing](CONTRIBUTING.md)

</div>

```
herdr plugin install zgxme/herdr-webhook-notify
herdr plugin action invoke herdr-webhook-notify.init
herdr plugin action invoke herdr-webhook-notify.test
```

## Why another notify plugin

Herdr already shows in-app toasts, but they only exist inside Herdr. This plugin
pushes notifications to where you actually are: your phone, your team chat, or
your own alerting gateway.

It also fixes the two things that make naive `done`-only hooks feel broken:

- **Watched panes.** Herdr reports a finished turn as `done` only while the
  completion is unseen. When the pane sits in the tab you are looking at, the
  same event arrives as `idle`, so a hook that only matches `done` silently
  drops it. This plugin keeps the previous status per pane and treats
  `working|blocked -> idle` as a completion too.
- **Missing context.** Event payloads carry no task title. The plugin reads the
  pane through the Herdr CLI to fill in the task summary (the agent's terminal
  title), workspace, tab, directory and git branch.

## Requirements

- Herdr 0.9.0 or newer
- Python 3.9 or newer (`python3` on `PATH`). No pip packages are needed: TOML
  parsing falls back to a vendored copy of tomli on Python 3.9 and 3.10.

## Install

```bash
herdr plugin install zgxme/herdr-webhook-notify
herdr plugin config-dir herdr-webhook-notify     # prints the config directory
herdr plugin action invoke herdr-webhook-notify.init
```

`init` writes a commented `config.toml` filled with every supported provider.
Enable one, add your secret, and test it:

```bash
# config.toml
[providers.slack]
enabled = true
webhook_url = "${SLACK_WEBHOOK}"

# .env in the same directory
SLACK_WEBHOOK=https://hooks.slack.com/services/...
```

```bash
herdr plugin action invoke herdr-webhook-notify.test
herdr plugin action invoke herdr-webhook-notify.status
```

For local development:

```bash
git clone https://github.com/zgxme/herdr-webhook-notify
herdr plugin link ./herdr-webhook-notify
```

## Providers

| provider | setup | notes |
| --- | --- | --- |
| `feishu` | custom bot webhook, optional signing secret | interactive card by default, `format = "text"` available |
| `lark` | same custom bot protocol as Feishu, hosted on `open.larksuite.com` | interactive card, optional signing secret |
| `dingtalk` | custom robot webhook, optional `secret` for signing | markdown message |
| `wecom` | group robot `key` or full webhook URL | markdown message |
| `slack` | incoming webhook URL | Block Kit, mrkdwn |
| `discord` | channel webhook URL | embed, optional `username`, `content` mention |
| `teams` | incoming webhook URL | MessageCard |
| `google_chat` | space webhook URL | text message |
| `telegram` | `bot_token` + `chat_id` | optional `parse_mode = "HTML"` or `"MarkdownV2"` |
| `ntfy` | topic, optional self-hosted `url` and `token` | priority mapped from event kind |
| `generic` | any `url` | full control over method, headers and body |

Per-provider details, including how to obtain each webhook, live in
[docs/providers.md](docs/providers.md).

## What triggers a notification

| Situation | Event status | Kind | Default |
| --- | --- | --- | --- |
| Turn finished while you were elsewhere | `done` | `done` | notify |
| Turn finished while you were watching that pane | `idle` | `done` | notify |
| Agent waits for approval or an answer | `blocked` | `blocked` | notify |
| Herdr loses track of the agent mid-turn | `unknown` | `unknown` | notify |
| Agent process exits, or its pane is closed | `pane.exited`, `pane.closed` | `exited` | notify |
| Agent starts working | `working` | - | ignored |
| Agent becomes idle at startup | `idle` | - | ignored |

Herdr has no explicit "failed" state. `unknown` and `exited` are the closest
signals it exposes, and both are reported by default.

## Configuration

The config file lives in the plugin config directory printed by
`herdr plugin config-dir herdr-webhook-notify`. Secrets can stay in a `.env`
file next to it and be referenced as `${NAME}`; a variable that is already set
in the environment wins, so CI and secrets managers keep working.

```toml
language = "en"                      # en | zh-CN

[notify]
events = ["done", "blocked", "unknown", "exited"]
notify_when_focused = true           # false = only background panes
min_turn_seconds = 0                 # skip short turns
cooldown_seconds = 5                 # de-duplicate per pane and kind
quiet_hours = ["22:00-08:00"]        # local time, supports overnight ranges
quiet_hours_exempt = ["blocked"]     # kinds that ignore quiet hours
include_workspaces = []              # * wildcards, case-insensitive
exclude_workspaces = []
include_tabs = []
exclude_tabs = []
include_agents = []
exclude_agents = []

[http]
timeout_seconds = 5
retries = 1                          # retried on 408/425/429/5xx

[message]
title = "Herdr {status_label}: {task}"
body = """
**Status**: {status_label}
**Workspace**: {workspace}
**Task**: {task}
"""

[messages]
"status.done" = "All done"

[providers.slack]
enabled = true
webhook_url = "${SLACK_WEBHOOK}"
events = ["blocked"]                 # optional per-provider override
language = "en"                      # optional per-provider language
```

### Placeholders

`{status}`, `{status_label}`, `{kind}`, `{session}`, `{workspace}`,
`{workspace_id}`, `{tab}`, `{tab_id}`, `{task}`, `{agent}`, `{pane_id}`,
`{cwd}`, `{branch}`, `{duration}`, `{duration_seconds}`, `{host}`, `{time}`.

Unknown placeholders are left as-is; lines whose only value is empty are
removed, so optional fields like `{branch}` do not leave dangling labels.

### Language

English is the default. Set `language = "zh-CN"` globally or per provider, or
override individual strings with the `[messages]` table. Adding a locale is a
small pull request: copy a block in `herdr_webhook_notify/i18n.py`.

## Actions

| action | what it does |
| --- | --- |
| `herdr-webhook-notify.init` | write the commented starter `config.toml` |
| `herdr-webhook-notify.test` | send a sample notification to every enabled provider |
| `herdr-webhook-notify.status` | show config path, providers, filters and queue |
| `herdr-webhook-notify.mute` / `.resume` | silence or resume without editing config |

Bind one to a key if you like:

```toml
[[keys.command]]
key = "prefix+n"
type = "plugin_action"
command = "herdr-webhook-notify.test"
description = "test webhook notify"
```

## Reliability

- Hook runs never block Herdr: short timeout, exit code 0, errors on stderr.
- Requests are retried on 408/425/429/5xx with a small backoff.
- Notifications that still fail are stored in the plugin state directory and
  retried on the next event, up to three attempts.
- Token-ish parts of webhook URLs are redacted in logs and in `status` output.

Inspect what actually ran:

```bash
herdr plugin log list --plugin herdr-webhook-notify
```

## Troubleshooting

`test` reports "No provider is enabled" — run `init`, then set `enabled = true`.

A webhook is never hit — run `status`, it prints unresolved `${...}` variables
as warnings, and `herdr plugin log list` shows the hook's stderr.

Nothing is sent while you watch a pane — check `notify_when_focused`; with
`false` the plugin deliberately mirrors Herdr and stays quiet for the pane you
are looking at.

Everything is sent twice — Herdr emits both a status change and a process exit
when a pane disappears. The `cooldown_seconds` window (default 5s) collapses
those into one message.

## Development

```bash
python3 -m pytest -q      # 70 tests, no network access required
python3 -m ruff check .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for adding a provider.

## License

[MIT](LICENSE). The vendored tomli copy keeps its own MIT license in
`vendor/tomli/LICENSE`.
