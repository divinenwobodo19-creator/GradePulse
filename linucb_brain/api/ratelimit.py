"""
Dependency-free sliding-window rate limiter.

Used to damp brute-force on the auth endpoints. In-memory per-process; safe
for the single-worker dev/pilot footprint (a multi-worker deployment moves
this to a shared store, e.g. Redis, in a later phase).
"""
import time
import threading
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Return True if a request with `key` is under the limit (records it)."""
        now = time.monotonic()
        with self._lock:
            dq = self._hits[key]
            cutoff = now - self.window_seconds
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if len(dq) >= self.max_requests:
                return False
            dq.append(now)
            return True

    def reset(self):
        with self._lock:
            self._hits.clear()