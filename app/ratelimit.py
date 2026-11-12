"""In-memory rate limiting for the credential endpoints.

Single-process deployment, so a bounded in-process sliding window is the honest
implementation: no Redis, no external store, and counters the client can never
read or reset.
"""

from __future__ import annotations

import time
from collections import deque

from . import config

MAX_TRACKED_KEYS = 4096


class SlidingWindowLimiter:
    def __init__(self, *, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        hits = self._hits.get(key)
        if hits is None:
            if len(self._hits) >= MAX_TRACKED_KEYS:
                self._prune(cutoff)
            hits = deque()
            self._hits[key] = hits
        while hits and hits[0] < cutoff:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True

    def _prune(self, cutoff: float) -> None:
        for key in [key for key, hits in self._hits.items() if not hits or hits[-1] < cutoff]:
            del self._hits[key]

    def reset(self) -> None:
        self._hits.clear()


# 10 attempts per minute per client address and 8 per 15 minutes per account.
ip_limiter = SlidingWindowLimiter(limit=config.LOGIN_IP_LIMIT, window_seconds=60)
account_limiter = SlidingWindowLimiter(limit=config.LOGIN_ACCOUNT_LIMIT, window_seconds=15 * 60)


def client_ip(request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"
