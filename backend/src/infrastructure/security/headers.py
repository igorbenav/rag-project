"""Security headers applied to every response.

Adapted from sapari's middleware, with one difference: it omits a
Content-Security-Policy because Stripe Checkout and Stripe JS need external
script origins. Nothing here loads third-party code — the client is one bundle
served from this origin — so a restrictive policy costs nothing and closes the
gap that makes an API key in browser storage worth worrying about.
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

from ..config.settings import EnvironmentOption, get_settings
from .constants import CONTENT_SECURITY_POLICY, HSTS_MAX_AGE_SECONDS, SECURITY_HEADERS


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds the headers a browser needs to defend the page."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value

        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY

        # Only meaningful over TLS, and setting it in development would pin
        # localhost to https in the browser's HSTS store.
        if get_settings().ENVIRONMENT in (EnvironmentOption.PRODUCTION, EnvironmentOption.STAGING):
            response.headers["Strict-Transport-Security"] = f"max-age={HSTS_MAX_AGE_SECONDS}; includeSubDomains"

        return response
