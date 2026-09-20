# Contributing

Thanks for helping. Issues and pull requests are both welcome,
especially new providers and new locales.

## Development setup

```bash
git clone https://github.com/<you>/herdr-webhook-notify
cd herdr-webhook-notify
python3 -m pytest -q            # 70 tests, no network access needed
python3 -m ruff check .
```

Nothing needs to be installed: the plugin uses only the standard library and a
vendored `tomli` for Python 3.9 and 3.10. Use the Python version you want to
support for your tests.

To try it inside a real Herdr:

```bash
herdr plugin link ./herdr-webhook-notify
herdr plugin action invoke herdr-webhook-notify.init
herdr plugin log list --plugin herdr-webhook-notify
```

## Adding a provider

1. Create `herdr_webhook_notify/providers/<name>.py` exporting:
   - `NAME`, `TITLE`, `FLAVOR` (`markdown`, `slack` or `plain`)
   - `CONFIG_KEYS` (documentation only, used by `status` output)
   - `validate(options)` - raise `ValueError` with a helpful message
   - `build(options, message) -> Delivery` where `message` already carries the
     rendered `title` and `body` in your flavor
   - optionally `flavor(options)` when the flavor depends on config
2. Register the module in `herdr_webhook_notify/providers/__init__.py`.
3. Add a golden payload test in `tests/test_providers.py`.
4. Document it in `docs/providers.md` and add the table row in both READMEs.

Keep configuration validation in `validate`: a broken provider must fail with a
clear message instead of sending a malformed request.

## Adding a locale

Copy a block in `herdr_webhook_notify/i18n.py`, translate the status labels plus
the default title and body templates, and add a case to the language alias test
if the tag has an unusual form.

## Guidelines

- No runtime dependencies. Anything vendored must keep its license and be
  excluded from linting.
- A hook run must never raise: log to stderr and exit 0 for `notify`.
- Never log secret material; use `http.redact()` for URLs.
- Keep `herdr-plugin.toml` `version` in sync with `pyproject.toml` and
  `herdr_webhook_notify.__version__` (there is a test for it).
- Update `CHANGELOG.md` under `[Unreleased]`.

## Releasing

1. Bump the version in the three places above.
2. Move the `[Unreleased]` entries into a new version heading.
3. Tag `vX.Y.Z` and push. The marketplace picks up the new manifest version
   from the default branch automatically.
