"""Tests for the rate limiter."""

import pytest
from fastapi import HTTPException

from app.rate_limit import RateLimiter


class TestRateLimiter:
    def test_allows_requests_under_limit(self):
        limiter = RateLimiter(max_requests=5, window_secs=60)
        for _ in range(5):
            limiter.check("192.168.1.1")  # Should not raise

    def test_blocks_requests_over_limit(self):
        limiter = RateLimiter(max_requests=3, window_secs=60)
        for _ in range(3):
            limiter.check("10.0.0.1")
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("10.0.0.1")
        assert exc_info.value.status_code == 429

    def test_different_keys_independent(self):
        limiter = RateLimiter(max_requests=2, window_secs=60)
        for _ in range(2):
            limiter.check("ip-a")
        # ip-b should still be allowed
        limiter.check("ip-b")

    def test_429_detail_contains_limit_info(self):
        limiter = RateLimiter(max_requests=1, window_secs=30)
        limiter.check("key")
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("key")
        assert "1 per 30s" in exc_info.value.detail
