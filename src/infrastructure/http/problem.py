"""RFC 9457 problem details, and the handlers that produce them.

Every error leaving the API is `application/problem+json`, including
FastAPI's validation errors, which otherwise use their own shape.
"""

from typing import Any, Mapping, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from ...modules.common.exceptions import (
    DomainError,
    ResourceExistsError,
    ResourceNotFoundError,
    ValidationError,
)
from ..logging import get_logger

logger = get_logger(__name__)

CONTENT_TYPE = "application/problem+json"
PROBLEM_TYPE_PREFIX = "/problems"

# Deliberate status codes, mapped to a stable type slug and title.
# Anything unlisted falls back to a generic problem.
_TITLES: dict[int, tuple[str, str]] = {
    status.HTTP_400_BAD_REQUEST: ("bad-request", "Bad request"),
    status.HTTP_401_UNAUTHORIZED: ("unauthorized", "Unauthorized"),
    status.HTTP_403_FORBIDDEN: ("forbidden", "Forbidden"),
    status.HTTP_404_NOT_FOUND: ("not-found", "Resource not found"),
    status.HTTP_405_METHOD_NOT_ALLOWED: ("method-not-allowed", "Method not allowed"),
    status.HTTP_406_NOT_ACCEPTABLE: ("not-acceptable", "Not acceptable"),
    status.HTTP_409_CONFLICT: ("conflict", "Conflict"),
    status.HTTP_412_PRECONDITION_FAILED: ("precondition-failed", "Precondition failed"),
    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: ("content-too-large", "Content too large"),
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: ("unsupported-media-type", "Unsupported media type"),
    status.HTTP_422_UNPROCESSABLE_ENTITY: ("validation-failed", "Validation failed"),
    status.HTTP_429_TOO_MANY_REQUESTS: ("rate-limited", "Too many requests"),
    status.HTTP_500_INTERNAL_SERVER_ERROR: ("internal-error", "Internal server error"),
}


class FieldError(BaseModel):
    """One field-level validation failure."""

    field: str
    message: str


class ProblemDetail(BaseModel):
    """An RFC 9457 problem document. Declared so it appears in the OpenAPI schema."""

    type: str = Field(examples=["/problems/not-found"])
    title: str = Field(examples=["Resource not found"])
    status: int = Field(examples=[404])
    detail: Optional[str] = Field(default=None, examples=["No collection with id 3f2c…"])
    instance: Optional[str] = Field(default=None, examples=["/api/v1/collections/3f2c…"])
    errors: Optional[list[FieldError]] = None


class ProblemException(Exception):
    """Raise to return a specific problem document.

    Services raise `DomainError` subclasses instead; this is for the transport
    layer, where the status code is genuinely the thing being chosen.
    """

    def __init__(
        self,
        status_code: int,
        detail: Optional[str] = None,
        headers: Optional[Mapping[str, str]] = None,
        **extensions: Any,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.headers = dict(headers or {})
        self.extensions = extensions
        super().__init__(detail or _TITLES.get(status_code, ("", "Error"))[1])


def problem_response(
    request: Request,
    status_code: int,
    detail: Optional[str] = None,
    headers: Optional[Mapping[str, str]] = None,
    **extensions: Any,
) -> JSONResponse:
    """Build a problem+json response."""
    slug, title = _TITLES.get(status_code, ("error", "Error"))

    body: dict[str, Any] = {
        "type": f"{PROBLEM_TYPE_PREFIX}/{slug}",
        "title": title,
        "status": status_code,
        "instance": request.url.path,
    }
    if detail:
        body["detail"] = detail
    body.update({key: value for key, value in extensions.items() if value is not None})

    return JSONResponse(
        status_code=status_code,
        content=body,
        media_type=CONTENT_TYPE,
        headers=dict(headers or {}),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Route every error path through `problem_response`."""

    @app.exception_handler(ProblemException)
    async def _problem(request: Request, exc: ProblemException) -> JSONResponse:
        return problem_response(request, exc.status_code, exc.detail, exc.headers, **exc.extensions)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else None
        return problem_response(request, exc.status_code, detail, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
            for error in exc.errors()
        ]
        return problem_response(
            request,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The request body failed validation.",
            errors=errors,
        )

    @app.exception_handler(ResourceNotFoundError)
    async def _not_found(request: Request, exc: ResourceNotFoundError) -> JSONResponse:
        return problem_response(request, status.HTTP_404_NOT_FOUND, str(exc) or None)

    @app.exception_handler(ResourceExistsError)
    async def _exists(request: Request, exc: ResourceExistsError) -> JSONResponse:
        return problem_response(request, status.HTTP_409_CONFLICT, str(exc) or None)

    @app.exception_handler(ValidationError)
    async def _domain_validation(request: Request, exc: ValidationError) -> JSONResponse:
        return problem_response(request, status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc) or None)

    @app.exception_handler(DomainError)
    async def _domain(request: Request, exc: DomainError) -> JSONResponse:
        return problem_response(request, status.HTTP_400_BAD_REQUEST, str(exc) or None)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return problem_response(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "The server failed to process the request.",
        )
