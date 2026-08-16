"""In-process rate limiting (design §10.9): semaphores and token buckets.

Per backend/model: max_concurrency, requests/minute, tokens/minute, burst.
Distributed rate limiting is deferred until multi-process execution exists.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RateLimitSpec:
    key: str
    max_concurrency: int = 8
    requests_per_minute: int | None = None
    tokens_per_minute: int | None = None
    burst: int = 1


class TokenBucket:
    def __init__(self, rate_per_second: float, burst: float) -> None:
        self._rate = rate_per_second
        self._burst = burst
        self._tokens = burst
        self._updated = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._updated
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        self._updated = now

    def take(self, amount: float = 1.0) -> bool:
        self._refill()
        if self._tokens >= amount:
            self._tokens -= amount
            return True
        return False

    def sleep_for(self, amount: float = 1.0) -> float:
        self._refill()
        missing = max(amount - self._tokens, 0.0)
        return missing / self._rate if self._rate > 0 else 0.0


class RateLimiter:
    """Registry of semaphores and buckets keyed by backend/model."""

    def __init__(self) -> None:
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._buckets: dict[str, TokenBucket] = {}

    def register(self, spec: RateLimitSpec) -> None:
        self._semaphores[spec.key] = asyncio.Semaphore(spec.max_concurrency)
        if spec.requests_per_minute:
            self._buckets[spec.key] = TokenBucket(
                spec.requests_per_minute / 60.0, float(spec.burst)
            )

    def semaphore_for(self, key: str, default_concurrency: int = 8) -> asyncio.Semaphore:
        semaphore = self._semaphores.get(key)
        if semaphore is None:
            semaphore = asyncio.Semaphore(default_concurrency)
            self._semaphores[key] = semaphore
        return semaphore

    async def acquire_request(self, key: str) -> None:
        bucket = self._buckets.get(key)
        if bucket is not None and not bucket.take():
            await asyncio.sleep(bucket.sleep_for())

    def release_semaphore(self, key: str) -> None:
        semaphore = self._semaphores.get(key)
        if semaphore is not None:
            semaphore.release()

    def reset(self) -> None:
        self._semaphores.clear()
        self._buckets.clear()
