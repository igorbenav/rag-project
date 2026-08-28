"""Stored API keys. The key itself is never kept."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from ...infrastructure.database.models import TimestampMixin, UUIDMixin
from ...infrastructure.database.session import Base


class APIKey(Base, UUIDMixin, TimestampMixin):
    """One credential, stored as two hashes of the same secret.

    `lookup_hash` is SHA-256 and indexed, so finding the right row is a single
    query instead of bcrypt-comparing the presented key against every row.
    `secret_hash` is bcrypt, which is what actually verifies it: SHA-256 is
    fast enough to brute-force, which is the property that makes it a good
    index and a bad password hash.
    """

    __tablename__ = "api_keys"

    name: Mapped[str] = mapped_column(String(120))
    lookup_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    secret_hash: Mapped[str] = mapped_column(String(100))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
