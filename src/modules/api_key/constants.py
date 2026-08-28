"""Tuned values for API keys."""

# Identifies the credential in logs and pastes, and lets an accidentally
# committed key be found by grep.
KEY_PREFIX = "rag_"

# 32 bytes of entropy, url-safe encoded. Well past guessing range, and short
# enough to paste into a header by hand.
KEY_ENTROPY_BYTES = 32

# bcrypt truncates at 72 bytes; keys are far shorter, but the slice makes that
# explicit rather than depending on it.
MAX_HASHED_BYTES = 72
