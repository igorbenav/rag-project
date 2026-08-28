"""Shared Mistral client.

One client for the process: it owns an HTTP connection pool, so building a new
one per request would discard the pool on every call.
"""

from typing import Optional

from mistralai.client import Mistral
from mistralai.client.utils import BackoffStrategy, RetryConfig

from ..config.settings import get_settings
from ..logging import get_logger

logger = get_logger(__name__)

_client: Optional[Mistral] = None


class MistralNotConfiguredError(RuntimeError):
    """Raised when a Mistral call is attempted without an API key."""


def _retry_config() -> RetryConfig:
    """Exponential backoff, honouring 429 and 5xx.

    The SDK retries internally, so callers never implement their own loop.
    """
    settings = get_settings()
    return RetryConfig(
        strategy="backoff",
        backoff=BackoffStrategy(
            initial_interval=500,
            max_interval=8000,
            exponent=2.0,
            max_elapsed_time=settings.MISTRAL_MAX_RETRY_ELAPSED_MS,
        ),
        retry_connection_errors=True,
    )


def get_client() -> Mistral:
    """Return the process-wide client, building it on first use.

    Raises:
        MistralNotConfiguredError: if MISTRAL_API_KEY is unset.
    """
    global _client

    settings = get_settings()
    if not settings.MISTRAL_API_KEY:
        raise MistralNotConfiguredError(
            "MISTRAL_API_KEY is not set. Copy .env.example to .env and add a key from console.mistral.ai."
        )

    if _client is None:
        _client = Mistral(
            api_key=settings.MISTRAL_API_KEY,
            retry_config=_retry_config(),
            timeout_ms=settings.MISTRAL_TIMEOUT_MS,
        )
        logger.info("Mistral client initialised")

    return _client


async def close_client() -> None:
    """Release the connection pool. Called from the application lifespan."""
    global _client

    if _client is not None:
        await _client.__aexit__(None, None, None)
        _client = None
