"""HTTP delivery with bounded retries and secret-safe logging."""

from __future__ import annotations

import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

RETRY_STATUSES = {408, 425, 429, 500, 502, 503, 504}


@dataclass
class Response:
    ok: bool
    status: int = None
    body: str = ""
    error: str = ""


def redact(url: str) -> str:
    """Hide the secret part of a webhook URL before logging it."""
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return "<invalid url>"
    path = parsed.path
    segments = [segment for segment in path.split("/") if segment]
    if segments:
        segments[-1] = "***"
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    hidden = "&".join(f"{key}=***" for key, _ in query)
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, "/" + "/".join(segments), hidden, "")
    )


def send(url: str, body: bytes, headers: dict, timeout: float = 5, retries: int = 1, method: str = "POST") -> Response:
    attempt = 0
    while True:
        request = urllib.request.Request(url, data=body, headers=dict(headers or {}), method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8", "replace")
                return Response(True, response.status, payload, "")
        except urllib.error.HTTPError as exc:  # server answered with an error status
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:400]
            except Exception:  # pragma: no cover - body may be unreadable
                detail = ""
            if exc.code in RETRY_STATUSES and attempt < retries:
                attempt += 1
                time.sleep(0.5 * attempt)
                continue
            return Response(False, exc.code, detail, f"HTTP {exc.code}")
        except (urllib.error.URLError, OSError) as exc:
            if attempt < retries:
                attempt += 1
                time.sleep(0.5 * attempt)
                continue
            return Response(False, None, "", str(exc))
