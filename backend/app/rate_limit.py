"""
Rate limiting middleware for auth endpoints.

Uses an in-memory sliding-window counter keyed by client IP.
For production with multiple backend instances, swap to a Redis-backed store.
"""

import time
from collections import defaultdict
from typing import Dict, List

from fastapi import HTTPException, Request


class RateLimiter:
    """Simple in-memory sliding-window rate limiter."""

    def __init__(self, max_requests: int = 10, window_secs: int = 60) -> None:
        self.max_requests = max_requests
        self.window_secs = window_secs
        self._hits: Dict[str, List[float]] = defaultdict(list)

    def check(self, key: str) -> None:
        """Raise HTTPException 429 if *key* has exceeded the rate limit."""
        now = time.monotonic()
        cutoff = now - self.window_secs

        # Prune old entries
        hits = self._hits[key]
        self._hits[key] = [t for t in hits if t > cutoff]

        if len(self._hits[key]) >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Limit: {self.max_requests} per {self.window_secs}s.",
            )

        self._hits[key].append(now)


# ── Pre-configured limiters ──────────────────────────────────────────────────

# Login: 10 attempts per 60 s per IP
login_limiter = RateLimiter(max_requests=10, window_secs=60)

# Register: 5 accounts per 60 s per IP
register_limiter = RateLimiter(max_requests=5, window_secs=60)


def get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For from reverse proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
