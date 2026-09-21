# Events

This page documents what Herdr hands the plugin on every hook run, and how the
plugin turns it into a notification. It describes Herdr 0.9.0, the version the
plugin targets.

## Hooks

`herdr-plugin.toml` registers three event hooks. Herdr starts
`python3 run.py` with the event in the environment; `run.py` picks the `notify`
command because `HERDR_PLUGIN_EVENT` is set.

| hook | notification kind | fired when |
| --- | --- | --- |
| `pane.agent_status_changed` | `done`, `blocked`, `unknown` | an agent changes status |
| `pane.exited` | `exited` | the agent process died |
| `pane.closed` | `exited` | the pane was closed |

Status changes are classified in `herdr_webhook_notify/events.py`:

| `agent_status` | previous status | kind | notes |
| --- | --- | --- | --- |
| `blocked` | any | `blocked` | the agent waits for approval or an answer |
| `done` | any | `done` | completion of a pane you were not watching |
| `idle` | `working` or `blocked` | `done` | completion of a pane you were watching |
| `unknown` | `working` or `blocked` | `unknown` | Herdr lost track of the agent mid-turn |
| `working` | any | - | ignored, but starts the turn timer |
| `idle` | anything else | - | ignored, this is the startup idle state |

A `done` status followed by `idle` in the same pane does not produce a second
notification, because `idle` only counts while the previous status was
`working` or `blocked`.

`blocked` notifications are delayed by `notify.blocked_delay_seconds` (10
seconds by default) and re-checked before they are sent, because agents that
approve their own prompts only pass through that status for a moment. When the
pane has moved on, or the pane is gone, nothing is sent at all. When the status
cannot be read at that point the notification goes out anyway, since a missed
approval request is worse than a late one.

## Environment

| variable | contents |
| --- | --- |
| `HERDR_PLUGIN_EVENT` | dotted event name, e.g. `pane.agent_status_changed` |
| `HERDR_PLUGIN_EVENT_JSON` | the full event envelope, see below |
| `HERDR_PLUGIN_CONTEXT_JSON` | invocation context, see below |
| `HERDR_WORKSPACE_ID`, `HERDR_TAB_ID`, `HERDR_PANE_ID` | ids of the event scope |
| `HERDR_PLUGIN_CONFIG_DIR` | where `config.toml` and `.env` live |
| `HERDR_PLUGIN_STATE_DIR` | where `state.json` lives; Herdr points it at `~/.local/state/herdr/plugins/<plugin-id>` |
| `HERDR_PLUGIN_ROOT` | the installed or linked plugin directory |
| `HERDR_BIN_PATH` | path to the running Herdr binary |
| `HERDR_SOCKET_PATH`, `HERDR_ENV` | raw socket transport details |

`HERDR_PLUGIN_ACTION_ID` is set for actions (`init`, `test`, `status`,
`toggle`) instead of `HERDR_PLUGIN_EVENT`.

## Event envelope

`HERDR_PLUGIN_EVENT_JSON` is the JSON serialization of Herdr's `EventEnvelope`,
which only has two fields: `event` and `data`. Watch out for the naming: the
JSON uses snake_case, while `HERDR_PLUGIN_EVENT` uses dots.

```json
{
  "event": "pane_agent_status_changed",
  "data": {
    "type": "pane_agent_status_changed",
    "pane_id": "w1:p1",
    "workspace_id": "w1",
    "agent_status": "done",
    "agent": "codex",
    "title": "refactor auth",
    "display_agent": "codex",
    "state_labels": { "done": "Finished" }
  }
}
```

### `pane.agent_status_changed`

| field | notes |
| --- | --- |
| `type` | always `pane_agent_status_changed` |
| `pane_id` | e.g. `w1:p1` |
| `workspace_id` | e.g. `w1` |
| `agent_status` | `idle`, `working`, `blocked`, `done` or `unknown` |
| `agent` | detected agent kind, optional |
| `title` | presentation title, optional |
| `display_agent` | agent name the agent reports for display, optional |
| `state_labels` | labels set through `herdr pane report-metadata`, optional |

`title`, `display_agent` and `state_labels` only appear when something reports
pane metadata; agents do not fill them in by default.

### `pane.exited` and `pane.closed`

| field | notes |
| --- | --- |
| `type` | `pane_exited` or `pane_closed` |
| `pane_id` | e.g. `w1:p1` |
| `workspace_id` | e.g. `w1` |

## Context

`HERDR_PLUGIN_CONTEXT_JSON` describes the invocation. For pane events the
context is built for the pane the event belongs to, and the plugin only trusts
the pane-scoped fields when `focused_pane_id` matches the event pane.

| field | notes |
| --- | --- |
| `workspace_id`, `workspace_label`, `workspace_cwd` | workspace scope |
| `worktree` | `repo_key`, `repo_name`, `repo_root`, `checkout_path`, `is_linked_worktree`; only for workspaces that belong to a worktree group |
| `tab_id`, `tab_label` | tab scope |
| `focused_pane_id`, `focused_pane_cwd`, `focused_pane_agent`, `focused_pane_status` | pane scope |
| `selected_text`, `clicked_url`, `link_handler_id` | interaction scope, not used by this plugin |
| `invocation_source`, `correlation_id` | who invoked the command, not used by this plugin |

## Hookable events

Any of these can be registered in a manifest `[[events]]` block. This plugin
only uses the three listed above.

`workspace.created`, `workspace.updated`, `workspace.closed`,
`workspace.renamed`, `workspace.moved`, `workspace.reordered`,
`workspace.focused`, `worktree.created`, `worktree.opened`,
`worktree.removed`, `tab.created`, `tab.closed`, `tab.renamed`, `tab.moved`,
`tab.focused`, `pane.created`, `pane.closed`, `pane.focused`, `pane.moved`,
`pane.exited`, `pane.agent_detected`, `pane.agent_status_changed`.

`pane.updated`, `pane.output_changed`, `layout.updated` and
`workspace.metadata_updated` cannot be used as plugin event hooks, because
Herdr keeps them for socket API subscribers.

## Limits worth knowing

- The payload carries no timestamp and no exit code. `{time}` is the hook's own
  local time, and a non-zero exit status cannot be reported.
- `HERDR_SESSION` is not injected into plugin commands, so `{session}` is
  `default` in practice.
- Durations are measured by the plugin, not by Herdr: `state.json` records when
  a pane last entered `working`, and `{duration}` is the time between that
  transition and the notification. Waiting for approval (`blocked`) does not
  count, because resuming work resets the timer. When the plugin never saw the
  pane start working (it was installed mid-turn, `state.json` was removed, or
  the hook was dropped) the duration is unknown: the placeholder resolves to an
  empty value, the whole line is dropped from the message, and
  `min_turn_seconds` skips the check.
- If a notification fails, the request is queued in `state.json` with its URL,
  headers, body and HTTP method, and replayed on the next hook run.
