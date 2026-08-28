"""Conditional requests: ETag, If-None-Match and If-Match.

Two separate jobs share one header value.

`If-None-Match` on a read is about bandwidth: a client that already holds the
current representation gets 304 and no body. The UI polls an ingestion job
every second and a half while a document processes, and most of those polls
return something it already has.

`If-Match` on a write is about lost updates: a client that read a resource,
decided what to change, and sends the change back should not silently overwrite
someone else's edit made in between. Without it the last writer wins and
neither of them knows.
"""

import hashlib
import json
from typing import Any, Optional

from fastapi import Request, Response, status
from pydantic import BaseModel

from .problem import ProblemException


def etag_for(payload: Any) -> str:
    """A strong ETag over a representation's content.

    Derived from the serialised body rather than a version column, so it
    changes when and only when the bytes a client would receive change. Strong
    rather than weak (`W/`), because byte equality is exactly what is meant.
    """
    if isinstance(payload, BaseModel):
        content = payload.model_dump_json(by_alias=True)
    else:
        content = json.dumps(payload, sort_keys=True, default=str)

    return f'"{hashlib.sha256(content.encode()).hexdigest()[:32]}"'


def _tags(header: Optional[str]) -> list[str]:
    """Split a comma-separated list of entity tags."""
    if not header:
        return []
    return [tag.strip() for tag in header.split(",") if tag.strip()]


def matches(header: Optional[str], etag: str) -> bool:
    """Whether a client's tag list covers the current representation."""
    tags = _tags(header)
    return "*" in tags or etag in tags


def apply_read_conditions(request: Request, response: Response, payload: Any) -> Optional[Response]:
    """Set `ETag`, and return a 304 when the client already has this version.

    Returns None when the handler should send its body as usual.
    """
    etag = etag_for(payload)
    response.headers["ETag"] = etag

    if matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})

    return None


def require_if_match(request: Request, payload: Any, *, required: bool = False) -> None:
    """Reject a write whose precondition does not hold.

    Raises:
        ProblemException: 428 when a precondition is required and absent,
            412 when the client's tag does not match the current state.
    """
    header = request.headers.get("if-match")

    if header is None:
        if required:
            raise ProblemException(
                status.HTTP_428_PRECONDITION_REQUIRED,
                "This request must carry an If-Match header naming the version you read.",
            )
        return

    etag = etag_for(payload)
    if not matches(header, etag):
        raise ProblemException(
            status.HTTP_412_PRECONDITION_FAILED,
            "The resource changed since you read it. Fetch it again and retry.",
            headers={"ETag": etag},
        )
