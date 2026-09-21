import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _Handler(BaseHTTPRequestHandler):
    def _handle(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        self.server.requests.append(
            {
                "method": self.command,
                "path": self.path,
                "headers": {key.lower(): value for key, value in self.headers.items()},
                "body": body,
            }
        )
        status = self.server.next_status
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def do_POST(self):  # noqa: N802 - stdlib naming
        self._handle()

    def do_PUT(self):  # noqa: N802 - stdlib naming
        self._handle()

    def do_PATCH(self):  # noqa: N802 - stdlib naming
        self._handle()

    def log_message(self, *args):  # silence test output
        return


@pytest.fixture
def webhook_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    server.requests = []
    server.next_status = 200
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Keep every test away from the real Herdr config, state and socket."""
    for name in list(os_environ()):
        if name.startswith("HERDR_") or name.startswith("FEISHU_") or name.startswith("SLACK_"):
            monkeypatch.delenv(name, raising=False)
    config_dir = tmp_path / "config"
    state_dir = tmp_path / "state"
    config_dir.mkdir()
    state_dir.mkdir()
    monkeypatch.setenv("HERDR_PLUGIN_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("HERDR_PLUGIN_STATE_DIR", str(state_dir))
    monkeypatch.setenv("HERDR_BIN_PATH", "/bin/false")
    return {"config_dir": config_dir, "state_dir": state_dir}


def os_environ():
    import os

    return os.environ


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Record requested sleeps instead of performing them.

    The blocked delay and the retry backoff would otherwise slow the suite down.
    Returns the list of requested durations.
    """
    from herdr_webhook_notify import cli, http

    slept = []
    monkeypatch.setattr(cli.time, "sleep", slept.append)
    monkeypatch.setattr(http.time, "sleep", slept.append)
    return slept
