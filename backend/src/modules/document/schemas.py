"""Response schemas for the documents resource."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .models import DocumentStatus


class DocumentRead(BaseModel):
    """Representation of one ingested PDF."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    collection_id: UUID
    filename: str
    status: DocumentStatus
    page_count: int
    chunk_count: int = 0
    checksum: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created_at: datetime
    updated_at: Optional[datetime] = None
