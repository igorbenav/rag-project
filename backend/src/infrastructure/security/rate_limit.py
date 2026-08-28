"""Per-credential rate limiting with a token bucket.

A bucket refills continuously rather than resetting on a boundary, so a client
cannot spend a whole window's allowance in the last second and another straight
after. Buckets live in this process, which is correct while one container serves HTTP
and wrong the moment a second does: each would allow the full rate. The fix is
to move the counter behind a storage interface with a Redis backend — Redis is
already in this stack for the task queue — and it is noted in the README rather
than built, because nothing here runs more than one web process.
"""

import time
from dataclasses import dataclass, field
from typing import Dict

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

from ..config.settings import get_settings
from ..http.problem import problem_response
from ..logging import get_logger
from .constants import SWEEP_EVERY_REQUESTS

logger = get_logger(__name__)


@dataclass
class _Bucket:
    """Tokens available to one client, refilled by elapsed time."""

    tokens: float
    updated: float = field(default_factory=time.monotonic)

    def take(self, capacity: int, per_second: float) -> bool:
        now = time.monotonic()
        self.tokens = min(capacity, self.tokens + (now - self.updated) * per_second)
        self.updated = now

        if self.tokens < 1:
            return False

        self.tokens -= 1
        return True

    def seconds_until_next(self, per_second: float) -> int:
        return max(1, int((1 - self.tokens) / per_second) + 1)

    def is_spent(self, capacity: int, per_second: float) -> bool:
        """True when the bucket has refilled and holds no state worth keeping.

        A full bucket behaves exactly like one that has never been seen, so
        forgetting it changes nothing and frees the entry.
        """
        return self.tokens + (time.monotonic() - self.updated) * per_second >= capacity


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limits requests per API key, falling back to client address."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._buckets: Dict[str, _Bucket] = {}
        self._requests_since_sweep = 0

    def _identity(self, request: Request) -> str:
        """Prefer the key over the address: one client behind NAT is one client."""
        presented = request.headers.get("X-API-Key")
        if presented:
            return f"key:{presented[-12:]}"
        return f"ip:{request.client.host if request.client else 'unknown'}"

    def _maybe_sweep(self, capacity: int, per_second: float) -> None:
        """Drop refilled buckets periodically, so the keyspace stays bounded."""
        self._requests_since_sweep += 1
        if self._requests_since_sweep < SWEEP_EVERY_REQUESTS:
            return

        self._requests_since_sweep = 0
        spent = [key for key, bucket in self._buckets.items() if bucket.is_spent(capacity, per_second)]
        for key in spent:
            del self._buckets[key]

        if spent:
            logger.debug("Swept %d refilled rate-limit buckets", len(spent))

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()
        if not settings.RATE_LIMIT_ENABLED or request.url.path.startswith(settings.RATE_LIMIT_EXEMPT_PREFIXES):
            return await call_next(request)

        capacity = settings.RATE_LIMIT_BURST
        per_second = settings.RATE_LIMIT_PER_MINUTE / 60.0

        self._maybe_sweep(capacity, per_second)

        identity = self._identity(request)
        bucket = self._buckets.setdefault(identity, _Bucket(tokens=float(capacity)))

        if not bucket.take(capacity, per_second):
            retry_after = bucket.seconds_until_next(per_second)
            logger.info("Rate limited %s, retry after %ds", identity, retry_after)
            return problem_response(
                request,
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Rate limit of {settings.RATE_LIMIT_PER_MINUTE} requests per minute exceeded.",
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
