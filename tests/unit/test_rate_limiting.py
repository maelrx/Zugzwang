"""Rate limiting and budget integration tests."""

from __future__ import annotations

import asyncio

import pytest

from zugzwang_runtime.execution.rate_limiting import RateLimiter, RateLimitSpec, TokenBucket


@pytest.mark.unit
class TestTokenBucket:
    def test_bucket_depletes_and_refills(self) -> None:
        bucket = TokenBucket(rate_per_second=100.0, burst=2.0)
        assert bucket.take()
        assert bucket.take()
        assert not bucket.take()

    def test_sleep_for_positive(self) -> None:
        bucket = TokenBucket(rate_per_second=10.0, burst=1.0)
        assert bucket.take()
        wait = bucket.sleep_for()
        assert wait > 0.05


@pytest.mark.unit
@pytest.mark.asyncio
class TestRateLimiter:
    async def test_semaphore_limits_concurrency(self) -> None:
        limiter = RateLimiter()
        limiter.register(RateLimitSpec(key="m", max_concurrency=2))
        active = 0
        peak = 0

        async def worker() -> None:
            nonlocal active, peak
            semaphore = limiter.semaphore_for("m")
            async with semaphore:
                active += 1
                peak = max(peak, active)
                await asyncio.sleep(0.02)
                active -= 1

        await asyncio.gather(*[worker() for _ in range(8)])
        assert peak == 2

    async def test_request_bucket_waits_when_empty(self) -> None:
        limiter = RateLimiter()
        limiter.register(RateLimitSpec(key="m", max_concurrency=8, requests_per_minute=60, burst=1))
        started = asyncio.get_event_loop().time()
        for _ in range(2):
            await limiter.acquire_request("m")
        elapsed = asyncio.get_event_loop().time() - started
        assert elapsed >= 0.9, "second request must wait for the token bucket"
