"""Reusable column mixins shared by every model.

`Base` itself lives in `session.py`, next to the engine that binds it.
"""

import uuid as uuid_pkg
from datetime import UTC, datetime

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, MappedAsDataclass, mapped_column


class UUIDMixin(MappedAsDataclass):
    """Adds a UUID primary key, generated client-side.

    `default_factory` rather than `default` so the id exists on the object
    before the row is flushed, letting a handler build a Location header
    without a round trip.
    """

    id: Mapped[uuid_pkg.UUID] = mapped_column(
        UUID,
        primary_key=True,
        default_factory=uuid_pkg.uuid4,
        server_default=text("gen_random_uuid()"),
        init=False,
    )


class TimestampMixin(MappedAsDataclass):
    """Adds timezone-aware creation and update timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(UTC),
        nullable=False,
        init=False,
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(UTC),
        nullable=True,
        init=False,
    )
