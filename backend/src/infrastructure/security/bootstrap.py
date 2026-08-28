"""First-run credential, so the service is usable immediately after starting."""

from ..logging import get_logger

logger = get_logger(__name__)


async def bootstrap_api_key() -> None:
    """Create and log a key when none exist yet.

    Printing a secret to the log is a development convenience, not a pattern to
    keep: anything with access to the logs gets the key. Set
    API_KEY_BOOTSTRAP=false and mint keys with scripts/create_api_key.py once
    the logs are not private.
    """
    from ...modules.api_key.service import APIKeyService
    from ..database.session import local_session

    service = APIKeyService()
    async with local_session() as db:
        if await service.count(db):
            return
        _, key = await service.create("bootstrap", db)

    logger.warning("No API keys existed, so one was created for development: %s", key)
