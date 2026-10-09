"""In-memory rate limiter for login attempts (no Redis dependency).

A simple fixed-window counter keyed by client IP. Adequate for a single-process
local deployment; swap for a shared store if scaling horizontally.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict

from app.config import settings


class LoginRateLimiter:
    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> None:
        cutoff = now - self.window_seconds
        self._hits[key] = [t for t in self._hits[key] if t > cutoff]

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            if len(self._hits[key]) >= self.max_attempts:
                return False
            self._hits[key].append(now)
            return True

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


login_limiter = LoginRateLimiter(
    max_attempts=settings.login_rate_limit_attempts,
    window_seconds=settings.login_rate_limit_window_seconds,
)
