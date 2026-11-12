"""Outbound HTTP health probes.

The probe runs in a worker thread (stdlib urllib) with a hard 2.5s timeout, so a
dead LAN host records `down` instead of stalling the async loop. Only absolute
http/https URLs ever reach this module - the write paths reject anything else.
"""

from __future__ import annotations

import asyncio
import http.client
import socket
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from . import config

USER_AGENT = f"Hearth/{config.APP_VERSION} (homelab health check)"


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def probe_url_sync(url: str, timeout: float | None = None) -> tuple[str, int | None, str]:
    """Return (status, latency_ms, message) for one URL. Never raises."""
    timeout = timeout or config.PROBE_TIMEOUT_SECONDS
    if urlsplit(url).scheme.lower() not in {"http", "https"}:
        return "down", None, "unsupported scheme"

    started = time.perf_counter()
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read(64)  # read a byte of the body so the status is real
            latency = _elapsed_ms(started)
            if response.status >= 400:
                return "down", latency, f"HTTP {response.status}"
            return "up", latency, f"HTTP {response.status}"
    except urllib.error.HTTPError as error:
        return "down", _elapsed_ms(started), f"HTTP {error.code}"
    except urllib.error.URLError as error:
        reason = error.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return "down", _elapsed_ms(started), "timeout"
        return "down", _elapsed_ms(started), str(reason)[:120] or "unreachable"
    except (TimeoutError, socket.timeout):
        return "down", _elapsed_ms(started), "timeout"
    except (OSError, ValueError, http.client.HTTPException) as error:
        return "down", _elapsed_ms(started), str(error)[:120] or "unreachable"


async def probe(url: str, timeout: float | None = None) -> dict:
    status, latency_ms, message = await asyncio.to_thread(probe_url_sync, url, timeout)
    return {"status": status, "latency_ms": latency_ms, "message": message}
