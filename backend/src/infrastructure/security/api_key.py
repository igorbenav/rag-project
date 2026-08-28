"""Authenticating requests by API key."""

from typing import Annotated, Optional

from fastapi import Depends, Request, status
from fastapi.security import APIKeyHeader

from ...modules.api_key.models import APIKey
from ...modules.api_key.service import APIKeyService
from ..config.settings import get_settings
from ..http.problem import ProblemException
from .constants import API_KEY_HEADER

_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


async def require_api_key(
    request: Request,
    presented: Annotated[Optional[str], Depends(_header)] = None,
) -> Optional[APIKey]:
    """Reject the request unless it carries a valid key.

    Does nothing when API_KEY_REQUIRED is off, which is how the evaluation
    harness and the test suite talk to the service directly.
    """
    settings = get_settings()
    if not settings.API_KEY_REQUIRED:
        return None

    if not presented:
        raise ProblemException(
            status.HTTP_401_UNAUTHORIZED,
            f"Provide an API key in the {API_KEY_HEADER} header.",
            headers={"WWW-Authenticate": API_KEY_HEADER},
        )

    from ..database.session import local_session

    async with local_session() as db:
        record = await APIKeyService().authenticate(presented, db)

    if record is None:
        raise ProblemException(status.HTTP_401_UNAUTHORIZED, "That API key is not valid.")

    request.state.api_key_id = record.id
    return record
