"""Tuned values for authentication and rate limiting."""

# Header carrying the API key. Named rather than inlined because both the
# dependency and the 401 response that names it have to agree.
API_KEY_HEADER = "X-API-Key"

# Full sweep of refilled rate-limit buckets every N requests, rather than on
# every one. Without it a per-IP keyspace grows without bound, which turns a
# defence against abuse into a way to exhaust memory. The same cadence
# crudauth's in-memory backend uses.
SWEEP_EVERY_REQUESTS = 256


# --- Response headers ----------------------------------------------------

SECURITY_HEADERS = {
    # Stop the browser guessing a content type; a PDF chunk echoed back must
    # never be executed as script.
    "X-Content-Type-Options": "nosniff",
    # No framing, so the UI cannot be clickjacked into acting on a session.
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # Explicitly off. The legacy auditor introduced its own vulnerabilities and
    # is superseded by the policy below.
    "X-XSS-Protection": "0",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

# Everything the page needs comes from this origin: one bundle, one stylesheet,
# and API calls to itself. No third-party scripts means no allowlist to
# maintain and no gap to squeeze through.
#
# style-src allows 'unsafe-inline' because React writes inline styles for
# transitions; script-src does not, which is the half that matters.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "connect-src 'self'",
        "font-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)

# Two years, the value browsers require for preload-list eligibility.
HSTS_MAX_AGE_SECONDS = 63072000
