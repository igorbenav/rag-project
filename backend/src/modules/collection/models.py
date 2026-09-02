"""A collection: the unit documents are ingested into and queried against."""

from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ...infrastructure.database.models import TimestampMixin, UUIDMixin
from ...infrastructure.database.session import Base


class Collection(Base, UUIDMixin, TimestampMixin):
    """A named set of documents with its own vector and keyword indexes."""

    __tablename__ = "collections"

    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000), default=None)
    extra_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)

    api_key_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("api_keys.id", ondelete="CASCADE"), index=True, default=None)
