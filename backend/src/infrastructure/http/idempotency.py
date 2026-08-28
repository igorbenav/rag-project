"""Idempotency keys, so a retried request does not repeat its side effect.

A client that uploads and then loses the connection cannot tell whether the
work started. Retrying is the only sensible move, and without a key the retry
ingests everything a second time. With one, the second request is answered from
the first request's result.

Kept in memory, which is correct while one process serves HTTP and wrong the
moment a second does — the same limitation as the rate limiter, and the same
fix: move the store behind Redis, which is already in this stack.
"""

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from fastapi import Request, status

from ..logging import get_logger
from .constants import IDEMPOTENCY_HEADER, IDEMPOTENCY_TTL_SECONDS
from .problem import ProblemException

logger = get_logger(__name__)


@dataclass
class _Record:
    """What a completed request returned, and when."""

    fingerprint: str
    payload: Any
    stored: float


class IdempotencyStore:
    """Remembers the outcome of keyed requests for a while."""

    def __init__(self) -> None:
        self._records: Dict[str, _Record] = {}

    def _expired(self, record: _Record) -> bool:
        return time.monotonic() - record.stored > IDEMPOTENCY_TTL_SECONDS

    def get(self, key: str, fingerprint: str) -> Optional[Any]:
        """The earlier result for this key, if the request is the same one.

        Raises:
            ProblemException: 422 when the key was used for a different
                request. Reusing a key with new content is a client bug, and
                returning the old result would hide it.
        """
        record = self._records.get(key)
        if record is None:
            return None

        if self._expired(record):
            del self._records[key]
            return None

        if record.fingerprint != fingerprint:
            raise ProblemException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"{IDEMPOTENCY_HEADER} was already used for a different request.",
            )

        logger.info("Replaying the stored result for idempotency key %s", key[:8])
        return record.payload

    def put(self, key: str, fingerprint: str, payload: Any) -> None:
        self._prune()
        self._records[key] = _Record(fingerprint=fingerprint, payload=payload, stored=time.monotonic())

    def _prune(self) -> None:
        """Drop expired records, so the keyspace stays bounded."""
        for key in [key for key, record in self._records.items() if self._expired(record)]:
            del self._records[key]


idempotency_store = IdempotencyStore()


def idempotency_key(request: Request) -> Optional[str]:
    """The key a client supplied, if any. Absent means "do the work"."""
    key = request.headers.get(IDEMPOTENCY_HEADER)
    return key.strip() or None if key else None
