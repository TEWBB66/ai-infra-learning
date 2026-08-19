"""In-memory rate limiting for inference requests."""

from __future__ import annotations

from threading import Lock
import time


class FixedWindowRateLimiter:
    def __init__(
        self,
        enabled: bool = False,
        max_requests: int = 60,
        window_seconds: int = 60,
    ):
        self.enabled = enabled
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.rejected_total = 0
        self._clients = {}
        self._lock = Lock()

    def allow(self, client_id: str, now: float | None = None) -> bool:
        if not self.enabled:
            return True

        if self.max_requests <= 0:
            with self._lock:
                self.rejected_total += 1
            return False

        current_time = time.monotonic() if now is None else now

        with self._lock:
            window_start, count = self._clients.get(client_id, (current_time, 0))

            if current_time - window_start >= self.window_seconds:
                window_start = current_time
                count = 0

            if count >= self.max_requests:
                self.rejected_total += 1
                return False

            self._clients[client_id] = (window_start, count + 1)
            return True

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "enabled": self.enabled,
                "max_requests": self.max_requests,
                "window_seconds": self.window_seconds,
                "active_clients": len(self._clients),
                "rejected_total": self.rejected_total,
            }
