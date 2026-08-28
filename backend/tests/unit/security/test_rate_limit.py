"""The token bucket. Time is controlled, so these are deterministic."""

import pytest
from src.infrastructure.security.rate_limit import _Bucket

CAPACITY = 5
PER_SECOND = 1.0


class Clock:
    """A monotonic clock the test advances by hand."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    instance = Clock()
    monkeypatch.setattr("src.infrastructure.security.rate_limit.time.monotonic", instance)
    return instance


def bucket_at(clock: Clock, tokens: float) -> _Bucket:
    """A bucket stamped with the fake clock.

    `updated` defaults from `time.monotonic` captured at class definition, so
    patching the module does not reach it; the test sets it explicitly.
    """
    return _Bucket(tokens=tokens, updated=clock.now)


class TestBurst:
    def test_a_full_bucket_allows_its_capacity_then_stops(self, clock: Clock) -> None:
        bucket = bucket_at(clock, float(CAPACITY))

        allowed = [bucket.take(CAPACITY, PER_SECOND) for _ in range(CAPACITY + 3)]

        assert allowed[:CAPACITY] == [True] * CAPACITY
        assert allowed[CAPACITY:] == [False, False, False]


class TestRefill:
    def test_tokens_return_continuously_rather_than_at_a_boundary(self, clock: Clock) -> None:
        """A fixed window would let a client spend twice the rate across it."""
        bucket = bucket_at(clock, 0.0)

        clock.advance(1.0)

        assert bucket.take(CAPACITY, PER_SECOND) is True

    def test_refill_never_exceeds_capacity(self, clock: Clock) -> None:
        bucket = bucket_at(clock, 0.0)

        clock.advance(3600)
        allowed = [bucket.take(CAPACITY, PER_SECOND) for _ in range(CAPACITY + 1)]

        assert allowed.count(True) == CAPACITY

    def test_a_partial_wait_returns_a_partial_allowance(self, clock: Clock) -> None:
        bucket = bucket_at(clock, 0.0)

        clock.advance(2.5)
        allowed = [bucket.take(CAPACITY, PER_SECOND) for _ in range(4)]

        assert allowed.count(True) == 2


class TestRetryAfter:
    def test_an_empty_bucket_reports_when_to_come_back(self, clock: Clock) -> None:
        bucket = bucket_at(clock, 0.0)

        assert bucket.seconds_until_next(PER_SECOND) >= 1

    def test_a_slower_rate_means_a_longer_wait(self, clock: Clock) -> None:
        bucket = bucket_at(clock, 0.0)

        assert bucket.seconds_until_next(0.1) > bucket.seconds_until_next(10.0)


class TestEviction:
    """A per-IP keyspace must not grow without bound; see crudauth's backend."""

    def test_a_refilled_bucket_holds_no_state_worth_keeping(self, clock: Clock) -> None:
        bucket = bucket_at(clock, 0.0)

        clock.advance(CAPACITY / PER_SECOND)

        assert bucket.is_spent(CAPACITY, PER_SECOND) is True

    def test_a_bucket_still_paying_off_its_burst_is_kept(self, clock: Clock) -> None:
        bucket = bucket_at(clock, 0.0)

        clock.advance(1.0)

        assert bucket.is_spent(CAPACITY, PER_SECOND) is False

    def test_a_partly_used_bucket_is_kept(self, clock: Clock) -> None:
        bucket = bucket_at(clock, float(CAPACITY))
        bucket.take(CAPACITY, PER_SECOND)

        assert bucket.is_spent(CAPACITY, PER_SECOND) is False
