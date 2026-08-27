"""Request and response schemas for the collections resource."""

from datetime import datetime
from typing import Annotated, Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CollectionCreate(BaseModel):
    """Body of `POST /collections`: everything a client may set."""

    name: Annotated[str, Field(min_length=1, max_length=255, description="Human-readable name.")]
    description: Optional[str] = Field(default=None, max_length=1000)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Free-form metadata.")


class CollectionRead(BaseModel):
    """Representation of a collection, in the order it is serialised."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    document_count: int = 0
    chunk_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None
