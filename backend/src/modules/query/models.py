"""A query and its answer, kept so both stay addressable."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import JSON, Boolean, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...infrastructure.database.models import TimestampMixin, UUIDMixin
from ...infrastructure.database.session import Base


class Query(Base, UUIDMixin, TimestampMixin):
    """One question asked of a collection, with what was answered and why.

    Persisted rather than computed and discarded: an answer that can be fetched
    again is an audit trail, a shareable link, and a way to revisit a reply
    without paying for the model a second time.
    """

    __tablename__ = "queries"

    collection_id: Mapped[UUID] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)

    answered: Mapped[bool] = mapped_column(Boolean, default=True)
    intent: Mapped[str] = mapped_column(String(32), default="question")
    refusal_reason: Mapped[Optional[str]] = mapped_column(String(64), default=None)
    disclaimer: Mapped[Optional[str]] = mapped_column(Text, default=None)

    answer_list: Mapped[List[str]] = mapped_column(JSON, default_factory=list)
    answer_table: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)

    citations: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default_factory=list)
    unsupported_claims: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default_factory=list)
    evidence_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    trace: Mapped[Dict[str, Any]] = mapped_column(JSON, default_factory=dict)
    elapsed_seconds: Mapped[float] = mapped_column(Float, default=0.0)
