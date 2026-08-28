"""A document: one ingested PDF, belonging to a collection."""

import enum
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import JSON, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ...infrastructure.database.models import TimestampMixin, UUIDMixin
from ...infrastructure.database.session import Base


class DocumentStatus(str, enum.Enum):
    """Where a document is in the ingestion pipeline."""

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Document(Base, UUIDMixin, TimestampMixin):
    """One PDF: its provenance, its ingestion outcome, and its page count."""

    __tablename__ = "documents"

    collection_id: Mapped[UUID] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(512), index=True)

    checksum: Mapped[str] = mapped_column(String(64), index=True)

    ingestion_job_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("ingestion_jobs.id", ondelete="SET NULL"), index=True, default=None
    )

    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", values_callable=lambda e: [m.value for m in e]),
        default=DocumentStatus.PENDING,
    )
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(String(1000), default=None)
    extra_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)
