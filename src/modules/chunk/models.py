"""A chunk: the unit that gets embedded, retrieved, and cited."""

from typing import Any, Dict, List, Optional

from sqlalchemy import ARRAY, JSON, Float, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ...infrastructure.database.models import TimestampMixin, UUIDMixin
from ...infrastructure.database.session import Base


class Chunk(Base, UUIDMixin, TimestampMixin):
    """A span of text with its embedding and the page it came from.

    `page` and `ordinal` are columns rather than metadata because every
    citation returns them and retrieval orders by them.
    """

    __tablename__ = "chunks"

    document_id: Mapped[Uuid] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    page: Mapped[int] = mapped_column(Integer)
    ordinal: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[List[float]] = mapped_column(ARRAY(Float))
    extra_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
