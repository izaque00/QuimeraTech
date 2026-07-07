"""
Rate limiter for Quimera API — token bucket algorithm.
Supports both in-memory and Redis-backed modes.
"""
import time
import threading
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TokenBucket:
    """Thread-safe token bucket rate limiter."""

    def __init__(self, rate: float, burst: int, name: str = "default"):
        self.rate = rate          # tokens per second
        self.burst = burst        # max burst size
        self.name = name
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
            self._last_refill = now
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    @property
    def available(self) -> float:
        with self._lock:
            return self._tokens


class RateLimiter:
    """Multi-bucket rate limiter for API endpoints."""

    def __init__(self):
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def get_bucket(self, key: str, rate: float = 10.0, burst: int = 20) -> TokenBucket:
        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(rate=rate, burst=burst, name=key)
            return self._buckets[key]

    def is_allowed(self, key: str, rate: float = 10.0, burst: int = 20) -> bool:
        return self.get_bucket(key, rate, burst).consume(1)

    def get_stats(self) -> dict:
        return {k: {"available": v.available, "rate": v.rate, "burst": v.burst}
                for k, v in self._buckets.items()}


# Global singleton
rate_limiter = RateLimiter()
