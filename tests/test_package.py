import re
from pathlib import Path

from herdr_webhook_notify import __version__, _toml

ROOT = Path(__file__).resolve().parent.parent


def manifest() -> dict:
    return _toml.loads((ROOT / "herdr-plugin.toml").read_text(encoding="utf-8"))


def pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    return re.search(r'^version = "([^"]+)"', text, re.MULTILINE).group(1)


def test_versions_stay_in_sync():
    assert pyproject_version() == __version__
    assert manifest()["version"] == __version__


def test_manifest_metadata():
    data = manifest()
    assert data["id"] == "herdr-webhook-notify"
    assert re.fullmatch(r"[A-Za-z0-9._:-]+", data["id"])
    assert data["min_herdr_version"]
    assert data["description"]
    assert set(data["platforms"]) <= {"linux", "macos", "windows"}


def test_every_event_hook_is_declared_and_runnable():
    data = manifest()
    names = {entry["on"] for entry in data["events"]}
    # Events the plugin logic knows how to handle.
    assert "pane.agent_status_changed" in names
    assert "pane.exited" in names
    for entry in data["events"]:
        command = entry["command"]
        assert isinstance(command, list) and command
        assert (ROOT / command[1]).is_file()


def test_actions_are_declared():
    data = manifest()
    ids = {entry["id"] for entry in data["actions"]}
    assert {"init", "test", "status", "mute", "resume"} <= ids
    for entry in data["actions"]:
        assert "." not in entry["id"]
        assert entry["title"]
        assert (ROOT / entry["command"][1]).is_file()


def test_provider_licence_is_vendored():
    assert (ROOT / "vendor" / "tomli" / "LICENSE").is_file()
