"""Generating, hashing and verifying API keys."""

import hashlib
import secrets

import bcrypt

from .constants import KEY_ENTROPY_BYTES, KEY_PREFIX, MAX_HASHED_BYTES


def generate_key() -> str:
    """Mint a new key. Returned once, then only its hashes are kept."""
    return f"{KEY_PREFIX}{secrets.token_urlsafe(KEY_ENTROPY_BYTES)}"


def lookup_hash(key: str) -> str:
    """Fast, indexable digest used to find the row.

    Not a security boundary — SHA-256 is cheap by design. It narrows the search
    to one row so bcrypt runs once instead of once per stored key.
    """
    return hashlib.sha256(key.encode()).hexdigest()


def secret_hash(key: str) -> str:
    """Slow digest that actually protects the key at rest."""
    return bcrypt.hashpw(key.encode()[:MAX_HASHED_BYTES], bcrypt.gensalt()).decode()


def verify(key: str, stored_hash: str) -> bool:
    """Constant-time comparison of a presented key against its bcrypt hash."""
    try:
        return bcrypt.checkpw(key.encode()[:MAX_HASHED_BYTES], stored_hash.encode())
    except ValueError:
        return False
