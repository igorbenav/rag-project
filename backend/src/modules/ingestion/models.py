"""The ingestion job: what a client polls after uploading."""

import enum
from typing import Optional
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from ...infrastructure.database.models import TimestampMixin, UUIDMixin
from ...infrastructure.database.session import Base


class IngestionStatus(str, enum.Enum):
    """Lifecycle of one upload request."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestionJob(Base, UUIDMixin, TimestampMixin):
    """One upload request, tracking the documents it produced.

    Exists because ingestion is unbounded work: the upload returns immediately
    and this is the resource the client polls.
    """

    __tablename__ = "ingestion_jobs"

    collection_id: Mapped[UUID] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), index=True)
    status: Mapped[IngestionStatus] = mapped_column(
        Enum(IngestionStatus, name="ingestion_status", values_callable=lambda e: [m.value for m in e]),
        default=IngestionStatus.PENDING,
    )
    total_documents: Mapped[int] = mapped_column(Integer, default=0)
    completed_documents: Mapped[int] = mapped_column(Integer, default=0)
    failed_documents: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(String(1000), default=None)


class UploadBlob(Base, TimestampMixin):
    """The uploaded bytes, held only until their document finishes ingesting.

    A separate table so that listing documents never drags megabytes of PDF
    into memory, and deleted on success so the database does not accumulate
    files it no longer needs. This is what makes a job resumable: a worker
    that dies mid-document finds the bytes still here when it restarts.
    """

    __tablename__ = "upload_blobs"

    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)
