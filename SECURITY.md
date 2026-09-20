# Security

## Reporting

Please report suspected vulnerabilities privately through GitHub's
"Report a vulnerability" flow on this repository rather than a public issue.

## What this plugin does

Like every Herdr plugin, it is ordinary code running with your user privileges.
It reads Herdr events, may call the Herdr CLI, and sends HTTP requests to the
endpoints you configure. Review `herdr-plugin.toml` and the Python sources
before linking or installing it.

## Secret handling

- Put webhook URLs and tokens in a `.env` next to `config.toml`, or in the
  process environment; both are read at runtime and never written by the
  plugin.
- Prefer read-only, scope-limited tokens, for example an ntfy token that can
  only publish to one topic.
- A webhook URL is a credential: anyone holding it can post to that channel.
  Rotate it if it leaks.
- `status` and log output redact the last path segment and all query values of
  configured URLs, but assume anything a plugin can read could end up in a
  crash report you paste elsewhere.

## Network behaviour

The plugin only connects to the URLs in your configuration. It does not phone
home, collect telemetry, or read agent transcripts; it reads pane metadata
(title, cwd, workspace, tab, agent kind) through the local Herdr socket.
