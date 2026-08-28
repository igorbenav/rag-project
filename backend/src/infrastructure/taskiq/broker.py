"""Taskiq broker: a Redis stream with a Redis result backend.

A stream rather than a list because streams acknowledge. With a list broker the
worker pops a task and owns it outright, so a process that dies mid-document
loses that task for good. A stream keeps the entry pending until the worker
acknowledges it, and another worker reclaims it once it has been idle too long.
"""

from taskiq import AsyncBroker
from taskiq_redis import RedisAsyncResultBackend, RedisStreamBroker

from ..config.settings import get_settings

settings = get_settings()


def create_broker() -> AsyncBroker:
    """Build the broker used by both the API and the worker."""
    return RedisStreamBroker(
        url=settings.TASKIQ_REDIS_URL,
        queue_name=settings.TASKIQ_QUEUE_NAME,
        idle_timeout=settings.TASKIQ_IDLE_TIMEOUT_MS,
        # The worker blocks on XREADGROUP, which outlives redis-py's default
        # socket timeout and would otherwise kill it on every idle poll.
        socket_timeout=None,
        socket_keepalive=True,
    ).with_result_backend(RedisAsyncResultBackend(redis_url=settings.TASKIQ_REDIS_URL))


broker = create_broker()
