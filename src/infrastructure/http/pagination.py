"""Offset pagination: a response envelope plus RFC 8288 `Link` headers."""

from typing import Annotated, Generic, Sequence, TypeVar
from urllib.parse import urlencode

from fastapi import Depends, Query, Request, Response
from pydantic import BaseModel, Field

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

T = TypeVar("T")


class Pagination(BaseModel):
    """Validated `limit`/`offset` from the query string."""

    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    offset: int = Field(default=0, ge=0)


def pagination_params(
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT, description="Items per page.")] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0, description="Items to skip.")] = 0,
) -> Pagination:
    """Dependency supplying pagination to a collection endpoint."""
    return Pagination(limit=limit, offset=offset)


PaginationDep = Annotated[Pagination, Depends(pagination_params)]


class Page(BaseModel, Generic[T]):
    """A slice of a collection, with the total so clients can size the range."""

    items: list[T]
    total: int
    limit: int
    offset: int


def _page_url(request: Request, limit: int, offset: int) -> str:
    """Rebuild the request URL with new pagination, preserving other filters."""
    params = {key: value for key, value in request.query_params.items() if key not in ("limit", "offset")}
    params["limit"] = str(limit)
    params["offset"] = str(offset)
    return f"{request.url.path}?{urlencode(params)}"


def link_header(request: Request, total: int, limit: int, offset: int) -> str:
    """Build the `Link` header value for a page.

    `next` is omitted on the last page and `prev` on the first, so a client can
    follow links until they run out rather than computing offsets.
    """
    links = [(_page_url(request, limit, 0), "first")]

    last_offset = max(0, ((total - 1) // limit) * limit) if total else 0
    links.append((_page_url(request, limit, last_offset), "last"))

    if offset > 0:
        links.append((_page_url(request, limit, max(0, offset - limit)), "prev"))
    if offset + limit < total:
        links.append((_page_url(request, limit, offset + limit), "next"))

    return ", ".join(f'<{url}>; rel="{rel}"' for url, rel in links)


def paginate(
    request: Request,
    response: Response,
    items: Sequence[T],
    total: int,
    pagination: Pagination,
) -> Page[T]:
    """Wrap a slice in a `Page` and set its `Link` header."""
    response.headers["Link"] = link_header(request, total, pagination.limit, pagination.offset)
    return Page[T](items=list(items), total=total, limit=pagination.limit, offset=pagination.offset)
