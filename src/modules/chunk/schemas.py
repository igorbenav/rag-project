"""Response schemas for the chunks resource."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChunkRead(BaseModel):
    """Representation of one chunk.

    The embedding is deliberately absent: a thousand floats no client needs,
    and citations return these inline.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    content: str
    page: int
    ordinal: int
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created_at: datetime
    updated_at: Optional[datetime] = None
