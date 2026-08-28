"""Tuned values for authentication and rate limiting."""

# Header carrying the API key. Named rather than inlined because both the
# dependency and the 401 response that names it have to agree.
API_KEY_HEADER = "X-API-Key"

# Full sweep of refilled rate-limit buckets every N requests, rather than on
# every one. Without it a per-IP keyspace grows without bound, which turns a
# defence against abuse into a way to exhaust memory. The same cadence
# crudauth's in-memory backend uses.
SWEEP_EVERY_REQUESTS = 256
