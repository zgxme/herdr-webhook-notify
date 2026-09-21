import pytest

from herdr_webhook_notify import config as config_mod


def write(tmp_path, text):
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_config_uses_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("HERDR_PLUGIN_CONFIG_DIR", str(tmp_path))
    cfg = config_mod.load()
    assert cfg.path is None
    assert cfg.language == "en"
    assert cfg.notify["events"] == ["done", "blocked", "unknown", "exited"]
    assert cfg.notify["notify_when_focused"] is True
    assert cfg.enabled == []
    assert cfg.warnings


def test_env_interpolation(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_HOOK", "https://example.com/hook")
    path = write(
        tmp_path,
        """
        [providers.generic]
        enabled = true
        url = "${MY_HOOK}"
        """,
    )
    cfg = config_mod.load(str(path))
    assert cfg.providers["generic"]["url"] == "https://example.com/hook"
    assert cfg.enabled == ["generic"]


def test_dotenv_file_is_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("HERDR_PLUGIN_CONFIG_DIR", str(tmp_path))
    (tmp_path / ".env").write_text("FROM_DOTENV=https://example.com/dotenv\n", encoding="utf-8")
    write(
        tmp_path,
        """
        [providers.generic]
        enabled = true
        url = "${FROM_DOTENV}"
        """,
    )
    cfg = config_mod.load()
    assert cfg.providers["generic"]["url"] == "https://example.com/dotenv"


def test_missing_env_variable_is_reported(tmp_path):
    path = write(
        tmp_path,
        """
        [providers.generic]
        enabled = true
        url = "${NOT_SET_ANYWHERE}"
        """,
    )
    cfg = config_mod.load(str(path))
    assert "NOT_SET_ANYWHERE" in cfg.missing_env


def test_unknown_provider_is_rejected(tmp_path):
    path = write(tmp_path, "[providers.nope]\nenabled = true\n")
    with pytest.raises(config_mod.ConfigError, match="unknown provider"):
        config_mod.load(str(path))


def test_provider_validation_surfaces_missing_options(tmp_path):
    path = write(tmp_path, "[providers.slack]\nenabled = true\n")
    with pytest.raises(config_mod.ConfigError, match="webhook_url"):
        config_mod.load(str(path))


def test_disabled_provider_is_not_validated(tmp_path):
    path = write(tmp_path, "[providers.slack]\nenabled = false\n")
    cfg = config_mod.load(str(path))
    assert cfg.enabled == []


def test_bad_language_is_rejected(tmp_path):
    with pytest.raises(config_mod.ConfigError, match="language"):
        config_mod.load(str(write(tmp_path, 'language = "klingon"\n')))


def test_language_aliases(tmp_path):
    cfg = config_mod.load(str(write(tmp_path, 'language = "zh_cn"\n')))
    assert cfg.language == "zh-CN"


def test_unknown_event_kind_is_rejected(tmp_path):
    with pytest.raises(config_mod.ConfigError, match="notify.events"):
        config_mod.load(str(write(tmp_path, '[notify]\nevents = ["exploded"]\n')))


def test_bad_quiet_hours_is_rejected(tmp_path):
    with pytest.raises(config_mod.ConfigError, match="quiet_hours"):
        config_mod.load(str(write(tmp_path, '[notify]\nquiet_hours = ["late"]\n')))


def test_example_config_is_valid():
    root = config_mod.plugin_root()
    cfg = config_mod.load(str(root / "examples" / "config.toml"))
    assert cfg.language == "en"
    assert cfg.enabled == []
    assert set(cfg.providers) == set(__import__(
        "herdr_webhook_notify.providers", fromlist=["names"]
    ).names())


def test_unknown_keys_are_reported_with_a_suggestion(tmp_path):
    path = write(
        tmp_path,
        """
        [notify]
        cooldown_second = 3

        [messages]
        "status.finished" = "done"

        [providers.slack]
        enabled = false
        webhook_urll = "https://example.com"
        """,
    )
    cfg = config_mod.load(str(path))
    joined = " | ".join(cfg.unknown_keys)
    assert "notify.cooldown_second" in joined and "cooldown_seconds" in joined
    assert "messages.status.finished" in joined
    assert "providers.slack.webhook_urll" in joined and "webhook_url" in joined
    assert any("unknown config key" in warning for warning in cfg.warnings)


def test_provider_specific_keys_are_known(tmp_path):
    path = write(
        tmp_path,
        """
        [providers.telegram]
        enabled = false
        bot_token = "token"
        chat_id = "chat"
        api_base = "https://example.test"

        [providers.wecom]
        enabled = false
        key = "robot"
        base_url = "https://example.test"

        [providers.generic]
        enabled = false
        url = "https://example.test"
        flavor = "plain"
        timeout_seconds = 12
        retries = 4
        """,
    )
    assert config_mod.load(str(path)).unknown_keys == []


def test_provider_timeout_must_be_a_positive_number(tmp_path):
    path = write(
        tmp_path,
        """
        [providers.slack]
        enabled = true
        webhook_url = "https://example.com"
        timeout_seconds = 0
        """,
    )
    with pytest.raises(config_mod.ConfigError, match="timeout_seconds"):
        config_mod.load(str(path))
