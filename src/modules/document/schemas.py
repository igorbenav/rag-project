"""Response schemas for the documents resource."""

from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..common.schemas import TimestampSchema
from .models import DocumentStatus


class DocumentRead(TimestampSchema, BaseModel):
    """Representation returned for a single document."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    collection_id: UUID
    filename: str
    checksum: str
    status: DocumentStatus
    page_count: int
    chunk_count: int = 0
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
