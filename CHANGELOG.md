# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `{repo}` and `{worktree}` placeholders, filled from the worktree Herdr
  reports for the workspace.
- `docs/events.md`, covering hook payloads, invocation context and their limits.
- `status` now prints the configured quiet hours and tab include/exclude lists.
- `notify.blocked_delay_seconds` (default 10) waits before reporting a blocked
  pane and re-checks it first, so agents that approve their own prompts no
  longer trigger a notification. `0` restores the immediate behaviour.
- `status` also reports `blocked_delay_seconds`, the HTTP timeout and retries,
  per-provider event filters, and whether custom message templates are in use.
- The READMEs document where `state.json` lives when Herdr runs the plugin.

### Fixed

- `providers.generic.method` is honoured. It was validated but ignored, so
  `PUT` and `PATCH` were sent as `POST`. Queued notifications keep their method
  when they are replayed.
- `quiet_hours` is normalized at load time, so a single string value is handled
  the same way as a list.
- README no longer claims `cooldown_seconds` merges a completion with a pane
  exit. Those are different kinds and are sent separately.

## [0.1.0] - 2026-09-20

### Added

- Herdr plugin manifest with `pane.agent_status_changed`, `pane.exited` and
  `pane.closed` event hooks.
- Completion detection that also covers `working|blocked -> idle`, which is how
  Herdr reports a turn that finishes while you watch the pane.
- Providers: feishu, dingtalk, wecom, slack, discord, teams, google_chat,
  telegram, ntfy, generic, plus `lark` for the international Feishu tenant.
- Configurable scope: event kinds, focused-pane policy, workspace/tab/agent
  include and exclude globs, quiet hours, minimum turn duration, cooldown.
- Bilingual messages (English default, `zh-CN`) with per-provider language
  overrides, custom templates and single-string overrides.
- Actions: init, test, status, mute, resume.
- Bounded retries plus a persisted queue for failed deliveries.
- 70 tests, ruff linting, CI matrix over Linux/macOS/Windows and Python 3.9/3.12.

[Unreleased]: https://github.com/zgxme/herdr-webhook-notify/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/zgxme/herdr-webhook-notify/releases/tag/v0.1.0
