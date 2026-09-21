"""Config loading, ${ENV} interpolation and validation."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import _toml, i18n, providers

ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
CONFIG_NAME = "config.toml"
SUPPORTED_EVENTS = ("done", "blocked", "unknown", "exited")

DEFAULTS = {
    "language": i18n.DEFAULT_LANGUAGE,
    "notify": {
        "events": ["done", "blocked", "unknown", "exited"],
        "notify_when_focused": True,
        "min_turn_seconds": 0,
        "cooldown_seconds": 5,
        "quiet_hours": [],
        "quiet_hours_exempt": ["blocked"],
        "include_workspaces": [],
        "exclude_workspaces": [],
        "include_tabs": [],
        "exclude_tabs": [],
        "include_agents": [],
        "exclude_agents": [],
    },
    "message": {"title": "", "body": ""},
    "messages": {},
    "http": {"timeout_seconds": 5, "retries": 1},
    "providers": {},
}


class ConfigError(Exception):
    """Raised when config.toml cannot be used."""


@dataclass
class Config:
    path: Path = None
    language: str = i18n.DEFAULT_LANGUAGE
    notify: dict = field(default_factory=dict)
    http: dict = field(default_factory=dict)
    message: dict = field(default_factory=dict)
    messages: dict = field(default_factory=dict)
    providers: dict = field(default_factory=dict)
    enabled: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    missing_env: list = field(default_factory=list)

    def provider_options(self, name: str) -> dict:
        return self.providers.get(name, {})

    def is_enabled(self, name: str) -> bool:
        return name in self.enabled


def plugin_root() -> Path:
    return Path(__file__).resolve().parent.parent


def candidate_paths(explicit=None) -> list:
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    env_override = os.environ.get("HERDR_WEBHOOK_NOTIFY_CONFIG")
    if env_override:
        candidates.append(Path(env_override).expanduser())
    config_dir = os.environ.get("HERDR_PLUGIN_CONFIG_DIR")
    if config_dir:
        candidates.append(Path(config_dir) / CONFIG_NAME)
    candidates.append(plugin_root() / CONFIG_NAME)
    return candidates


def load_env_files() -> list:
    """Load .env files so ${VAR} placeholders work without a shell wrapper."""
    loaded = []
    candidates = []
    config_dir = os.environ.get("HERDR_PLUGIN_CONFIG_DIR")
    if config_dir:
        candidates.append(Path(config_dir) / ".env")
    candidates.append(plugin_root() / ".env")
    for candidate in candidates:
        try:
            content = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        loaded.append(candidate)
    return loaded


def resolve_path(explicit=None, for_write: bool = False) -> Path:
    candidates = candidate_paths(explicit)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    if for_write:
        config_dir = os.environ.get("HERDR_PLUGIN_CONFIG_DIR")
        base = Path(config_dir) if config_dir else plugin_root()
        return base / CONFIG_NAME
    return candidates[0]


def interpolate(value, missing: set):
    if isinstance(value, str):
        def replace(match):
            name = match.group(1)
            env_value = os.environ.get(name)
            if env_value is None:
                missing.add(name)
                return match.group(0)
            return env_value

        return ENV_PATTERN.sub(replace, value)
    if isinstance(value, dict):
        return {key: interpolate(item, missing) for key, item in value.items()}
    if isinstance(value, list):
        return [interpolate(item, missing) for item in value]
    return value


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _string_list(value, key: str) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result = []
        for item in value:
            if not isinstance(item, str):
                raise ConfigError(f"{key}: expected a list of strings")
            result.append(item)
        return result
    raise ConfigError(f"{key}: expected a string or a list of strings")


def _number(value, key: str, minimum: float = 0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{key}: expected a number")
    if value < minimum:
        raise ConfigError(f"{key}: must be >= {minimum}")
    return value


def _parse_hour_range(value: str) -> tuple:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})", value.strip())
    if not match:
        raise ConfigError(f"notify.quiet_hours: bad range '{value}', expected HH:MM-HH:MM")
    start_h, start_m, end_h, end_m = (int(part) for part in match.groups())
    if start_h > 23 or end_h > 23 or start_m > 59 or end_m > 59:
        raise ConfigError(f"notify.quiet_hours: bad time in '{value}'")
    return (start_h * 60 + start_m, end_h * 60 + end_m)


def load(explicit=None) -> Config:
    load_env_files()
    path = resolve_path(explicit)
    raw = {}
    missing = set()

    if path.is_file():
        try:
            raw = _toml.loads(path.read_text(encoding="utf-8"))
        except _toml.TOMLDecodeError as exc:
            raise ConfigError(f"{path}: invalid TOML: {exc}") from exc
        except OSError as exc:
            raise ConfigError(f"{path}: cannot read file: {exc}") from exc
        raw = interpolate(raw, missing)
    else:
        path = None

    merged = _deep_merge(DEFAULTS, raw)
    config = Config(path=path)
    config.missing_env = sorted(missing)

    language = str(merged.get("language") or i18n.DEFAULT_LANGUAGE)
    known = known_language(language)
    if known is None:
        raise ConfigError(
            f"language: '{language}' is not supported, choose one of {', '.join(i18n.available())}"
        )
    config.language = known

    notify = dict(merged.get("notify") or {})
    events = _string_list(notify.get("events"), "notify.events")
    for event in events:
        if event not in SUPPORTED_EVENTS:
            raise ConfigError(
                f"notify.events: '{event}' is unknown, choose from {', '.join(SUPPORTED_EVENTS)}"
            )
    notify["events"] = events or list(SUPPORTED_EVENTS)
    notify["notify_when_focused"] = bool(notify.get("notify_when_focused", True))
    notify["min_turn_seconds"] = _number(notify.get("min_turn_seconds", 0), "notify.min_turn_seconds")
    notify["cooldown_seconds"] = _number(notify.get("cooldown_seconds", 5), "notify.cooldown_seconds")
    for key in (
        "include_workspaces",
        "exclude_workspaces",
        "include_tabs",
        "exclude_tabs",
        "include_agents",
        "exclude_agents",
        "quiet_hours_exempt",
    ):
        notify[key] = _string_list(notify.get(key), f"notify.{key}")
    quiet_hours = _string_list(notify.get("quiet_hours"), "notify.quiet_hours")
    notify["quiet_hours"] = quiet_hours
    notify["quiet_ranges"] = [_parse_hour_range(item) for item in quiet_hours]
    config.notify = notify

    http = dict(merged.get("http") or {})
    http["timeout_seconds"] = _number(http.get("timeout_seconds", 5), "http.timeout_seconds", 0.1)
    http["retries"] = int(_number(http.get("retries", 1), "http.retries"))
    config.http = http

    message = dict(merged.get("message") or {})
    config.message = {
        "title": str(message.get("title") or ""),
        "body": str(message.get("body") or ""),
    }

    messages = merged.get("messages") or {}
    if not isinstance(messages, dict):
        raise ConfigError("messages: expected a table")
    config.messages = {str(key): str(value) for key, value in messages.items()}

    provider_tables = merged.get("providers") or {}
    if not isinstance(provider_tables, dict):
        raise ConfigError("providers: expected a table")
    config.providers = {}
    for name, options in provider_tables.items():
        if not isinstance(options, dict):
            raise ConfigError(f"providers.{name}: expected a table")
        module = providers.get(name)
        if module is None:
            raise ConfigError(
                f"providers.{name}: unknown provider, available: {', '.join(providers.names())}"
            )
        options = dict(options)
        options["enabled"] = bool(options.get("enabled", False))
        events_override = options.get("events")
        if events_override is not None:
            options["events"] = _string_list(events_override, f"providers.{name}.events")
            for event in options["events"]:
                if event not in SUPPORTED_EVENTS:
                    raise ConfigError(
                        f"providers.{name}.events: '{event}' is unknown,"
                        f" choose from {', '.join(SUPPORTED_EVENTS)}"
                    )
        if "language" in options:
            options["language"] = str(options["language"])
        config.providers[name] = options
        if options["enabled"]:
            config.enabled.append(name)

    for name in config.enabled:
        module = providers.get(name)
        try:
            module.validate(config.providers[name])
        except Exception as exc:  # ProviderError and friends
            raise ConfigError(str(exc)) from exc

    if not config.enabled:
        config.warnings.append(
            "no provider is enabled, run 'init' and set enabled = true for at least one provider"
        )
    for name in config.missing_env:
        config.warnings.append(f"environment variable {name} is referenced but not set")

    return config


def known_language(language: str):
    if not language:
        return None
    target = language.strip().replace("_", "-").lower()
    for name in i18n.available():
        if name.lower() == target:
            return name
    base = target.split("-", 1)[0]
    for name in i18n.available():
        if name.lower().split("-", 1)[0] == base:
            return name
    return None
