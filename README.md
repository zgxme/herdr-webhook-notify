# herdr-webhook-notify

[![CI](https://github.com/zgxme/herdr-webhook-notify/actions/workflows/ci.yml/badge.svg)](https://github.com/zgxme/herdr-webhook-notify/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml) [![Platforms](https://img.shields.io/badge/platform-linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)](herdr-plugin.toml) [![Herdr plugin](https://img.shields.io/badge/Herdr-plugin-6E56CF.svg)](https://herdr.dev/plugins/) [![Providers](https://img.shields.io/badge/providers-11-2EB67D.svg)](#providers)

A [Herdr](https://herdr.dev) plugin that forwards agent notifications to the
webhook service you already use: Slack, Discord, Microsoft Teams, Google Chat,
Feishu, Lark, DingTalk, WeCom, Telegram, ntfy, or any custom HTTP endpoint.

[中文说明](README.zh-CN.md) | [Provider guides](docs/providers.md) | [Contributing](CONTRIBUTING.md)

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

The payload each hook receives, and how the plugin turns it into a
notification, is documented in [docs/events.md](docs/events.md).

## Configuration

The config file lives in the plugin config directory printed by
`herdr plugin config-dir herdr-webhook-notify`. Secrets can stay in a `.env`
file next to it and be referenced as `${NAME}`; a variable that is already set
in the environment wins, so CI and secrets managers keep working.

### Where the config comes from

The plugin looks for `config.toml` in this order:

1. `HERDR_WEBHOOK_NOTIFY_CONFIG` — path to an explicit file.
2. `HERDR_PLUGIN_CONFIG_DIR` + `/config.toml` — the plugin config directory.
3. `config.toml` in the plugin directory itself.

`.env` is read from `HERDR_PLUGIN_CONFIG_DIR` first, then from the plugin
directory. `HERDR_PLUGIN_STATE_DIR` moves `state.json`; Herdr points it at
`~/.local/state/herdr/plugins/<plugin-id>`, which is where the cooldowns, turn
timers and the retry queue actually live when the plugin runs as a hook.
`HERDR_BIN_PATH` tells the plugin which Herdr binary to call for pane,
workspace and tab labels.

Two list semantics are easy to get wrong:

- `notify.events = []` does not mean "notify nothing". An empty list falls back
  to all four kinds; remove the kinds you do not want instead.
- `providers.<name>.events = []` means "no per-provider filter" for the same
  reason, not "never notify".

```toml
language = "en"                      # en | zh-CN

[notify]
events = ["done", "blocked", "unknown", "exited"]
notify_when_focused = true           # false = only background panes
min_turn_seconds = 0                 # skip short turns
cooldown_seconds = 5                 # de-duplicate per pane and kind
blocked_delay_seconds = 10           # wait out a self-approving agent
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

### Top level

| key | type | default | meaning |
| --- | --- | --- | --- |
| `language` | string | `"en"` | Language of the built-in text: `en` or `zh-CN`. Can be overridden per provider. Any unknown value is a startup error, so typos fail loudly. |

### `[notify]`

| key | type | default | meaning |
| --- | --- | --- | --- |
| `events` | list | `["done", "blocked", "unknown", "exited"]` | Kinds allowed to notify. `done` covers both background completions and completions that happened while you watched the pane. |
| `notify_when_focused` | bool | `true` | `true` also notifies for the pane you are looking at; `false` mirrors Herdr and stays quiet for it. |
| `min_turn_seconds` | number | `0` | Ignore turns shorter than this many seconds. `0` disables the check. Applies to `done`, `blocked` and `unknown`. |
| `cooldown_seconds` | number | `5` | Suppress another notification for the same pane and kind inside this window, which collapses repeated `done` events for one pane into one message. Kinds are counted separately, so a completion plus a pane exit (`done` + `exited`) are still two messages. `0` disables. |
| `blocked_delay_seconds` | number | `10` | Wait this long before reporting a `blocked` pane, then re-check it: if the agent approved its own prompt and moved on, nothing is sent. `0` notifies immediately. |
| `quiet_hours` | list of `"HH:MM-HH:MM"` | `[]` | Local-time silent window; overnight ranges like `22:00-08:00` work. |
| `quiet_hours_exempt` | list | `["blocked"]` | Kinds that ignore `quiet_hours`, so approval requests still reach you at night. |
| `include_workspaces` | list of globs | `[]` | Only notify for these workspace labels, e.g. `["external-*"]`. Empty means all. |
| `exclude_workspaces` | list of globs | `[]` | Never notify for these workspace labels. Exclude wins over include. |
| `include_tabs` / `exclude_tabs` | list of globs | `[]` | Same rules, matched against the tab label or number. |
| `include_agents` / `exclude_agents` | list of globs | `[]` | Same rules, matched against the agent kind (`codex`, `claude`, `gemini`, ...). |

Globs are case-insensitive and use `*`/`?` wildcards.

### `[http]`

| key | type | default | meaning |
| --- | --- | --- | --- |
| `timeout_seconds` | number | `5` | Per-request timeout, minimum `0.1`. |
| `retries` | integer | `1` | Extra attempts on network errors and `408/425/429/5xx`. `0` means a single attempt. |

### `[message]` and `[messages]`

| key | type | default | meaning |
| --- | --- | --- | --- |
| `message.title` | string | localized | Template for the notification title. |
| `message.body` | string | localized | Template for the message body; multi-line TOML strings are fine. |
| `messages."status.done"` | string | built-in | Replace one built-in string. Available keys: `status.done`, `status.blocked`, `status.unknown`, `status.exited`, `status.test`, `title`, `body`. Quote the key in TOML because of the dot. |

### `[providers.<name>]`

Every provider accepts these three keys:

| key | type | default | meaning |
| --- | --- | --- | --- |
| `enabled` | bool | `false` | Turn this provider on. A disabled provider is not validated. |
| `events` | list | inherit | Optional per-provider subset, e.g. `["blocked"]` to only get approvals in Slack. |
| `language` | string | inherit | Optional per-provider language, useful when your team chats mix languages. |

| provider | required | optional |
| --- | --- | --- |
| `feishu` | `webhook_url` | `secret` (signature), `format` (`card`/`text`, default `card`), `card_title_prefix` |
| `lark` | `webhook_url` | same as `feishu` |
| `dingtalk` | `webhook_url` | `secret` (signature) |
| `wecom` | `key` or `webhook_url` | `base_url` |
| `slack` | `webhook_url` | - |
| `discord` | `webhook_url` | `username`, `avatar_url`, `content` (for mentions) |
| `teams` | `webhook_url` | - |
| `google_chat` | `webhook_url` | `thread_key` |
| `telegram` | `bot_token`, `chat_id` | `parse_mode` (`HTML`/`MarkdownV2`), `message_thread_id`, `disable_notification`, `api_base` |
| `ntfy` | `topic` | `url`, `token`, `priority`, `tags`, `click` |
| `generic` | `url` | `method` (`POST`/`PUT`/`PATCH`), `headers`, `body` (template), `content_type`, `flavor` (`markdown`/`slack`/`plain`) |

How to obtain each webhook is documented in [docs/providers.md](docs/providers.md).

### Placeholders

Use these in `message.title`, `message.body` and in `generic`'s `body` template:

| placeholder | meaning |
| --- | --- |
| `{status}` | Raw Herdr status of the event: `done`, `idle`, `blocked`, `unknown` or `exited`. A completion you watched arrives as `idle`. |
| `{status_label}` | Localized label of the notification kind, e.g. `Task finished`. |
| `{kind}` | Normalized kind: `done`, `blocked`, `unknown`, `exited` or `test`. |
| `{session}` | Herdr session name, `default` for the default session. |
| `{workspace}` | Workspace label, e.g. `external-fuzzer`; falls back to the workspace id. |
| `{workspace_id}` | Workspace id, e.g. `wD`. |
| `{tab}` | Tab label or number, e.g. `2`. |
| `{tab_id}` | Tab id, e.g. `wD:t2`. |
| `{task}` | Task summary: the pane terminal title, which agents set to their conversation title. Falls back to the pane id. |
| `{agent}` | Detected agent kind, e.g. `codex`, `claude`, `gemini`. |
| `{pane_id}` | Pane id, e.g. `wD:p1`. |
| `{cwd}` | Working directory of the pane. |
| `{branch}` | Current git branch of `{cwd}`; empty outside a repository. |
| `{repo}` | Repository name of the workspace worktree; empty outside a worktree workspace. |
| `{worktree}` | Checkout path of the workspace worktree; empty outside a worktree workspace. |
| `{duration}` | Turn duration, human formatted, e.g. `2m05s`. Measured from the moment the pane entered `working`, so time spent waiting for approval is not counted. Empty when unknown. |
| `{duration_seconds}` | The same duration as a raw number of seconds, for custom formatting. |
| `{host}` | Hostname of the machine running Herdr. |
| `{time}` | Local timestamp, `YYYY-MM-DD HH:MM:SS`. |

Unknown placeholders are kept as-is, so typos are visible instead of silently
disappearing. Lines whose only value resolves to empty are dropped, which is
why optional fields such as `{branch}` do not leave a dangling label. The same
emptiness makes `min_turn_seconds` skip its check, because there is no duration
to compare.

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
when a pane disappears, and those are two different kinds (`done` or `unknown`,
plus `exited`). `cooldown_seconds` only suppresses repeats of the same kind, so
it cannot merge the pair. Remove `exited` from `notify.events` (or from a
provider's `events` list) if you only care about completions.

## Development

```bash
python3 -m pytest -q      # 70 tests, no network access required
python3 -m ruff check .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for adding a provider.

## License

[MIT](LICENSE). The vendored tomli copy keeps its own MIT license in
`vendor/tomli/LICENSE`.
