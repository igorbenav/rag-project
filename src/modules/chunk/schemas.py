"""Response schemas for the chunks resource."""

from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..common.schemas import TimestampSchema


class ChunkRead(TimestampSchema, BaseModel):
    """Representation returned for a single chunk.

    The embedding is deliberately absent: it is a thousand floats that no
    client needs, and citations return these inline.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    content: str
    page: int
    ordinal: int
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
