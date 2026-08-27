"""Schema fragments shared across resource representations."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_serializer


class TimestampSchema(BaseModel):
    """Mirrors `TimestampMixin`, serialising both fields as ISO-8601."""

    created_at: datetime
    updated_at: Optional[datetime] = Field(default=None)

    @field_serializer("created_at", "updated_at")
    def serialize_timestamp(self, value: datetime | None, _info: Any) -> str | None:
        return value.isoformat() if value is not None else None
