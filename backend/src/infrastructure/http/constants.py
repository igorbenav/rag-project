"""Constants for the HTTP conventions this API applies uniformly."""

# Every link this API emits is rooted here. Named once so a version bump moves
# every href rather than only the ones someone remembered.
API_PREFIX = "/api/v1"

# RFC 9457. Every error response carries this, not application/json.
PROBLEM_CONTENT_TYPE = "application/problem+json"

# Problem types are relative URIs, resolved by the client against the request.
# Relative keeps them meaningful without owning a documentation domain.
PROBLEM_TYPE_PREFIX = "/problems"

# Page size when the client does not ask. Large enough that a demo corpus fits
# in one request, small enough that the default response stays readable.
DEFAULT_PAGE_LIMIT = 50

# Ceiling on limit. Caps the work one request can ask the database for; a
# client wanting everything pages through it.
MAX_PAGE_LIMIT = 200


# Header a client sends to make a retry safe.
IDEMPOTENCY_HEADER = "Idempotency-Key"

# How long a keyed result is replayable. Long enough to cover a client
# retrying through a network failure, short enough that a key reused days
# later is treated as new work rather than replayed.
IDEMPOTENCY_TTL_SECONDS = 86400
