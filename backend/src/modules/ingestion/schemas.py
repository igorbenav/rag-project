"""Response schemas for ingestion."""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .models import IngestionStatus


class IngestionJobRead(BaseModel):
    """Progress of one upload, and where its documents live."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    collection_id: UUID
    status: IngestionStatus
    total_documents: int
    completed_documents: int
    failed_documents: int
    error: Optional[str] = None
    document_ids: List[UUID] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime] = None

    links: Dict[str, str] = Field(default_factory=dict, serialization_alias="_links")
