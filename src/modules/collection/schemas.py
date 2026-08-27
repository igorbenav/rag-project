"""Request and response schemas for the collections resource."""

from typing import Annotated, Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..common.schemas import TimestampSchema


class CollectionBase(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=255, description="Human-readable name.")]
    description: Optional[str] = Field(default=None, max_length=1000)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Free-form metadata.")


class CollectionCreate(CollectionBase):
    """Body of `POST /collections`."""


class CollectionRead(TimestampSchema, CollectionBase):
    """Representation returned for a single collection."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_count: int = 0
    chunk_count: int = 0
