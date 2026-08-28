"""What generation produces."""

from dataclasses import dataclass, field
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class GeneratedAnswer(BaseModel):
    """Schema the model fills in when answering from passages."""

    answer: str = Field(description="The answer, or an empty string when the passages do not contain one.")
    cited: List[int] = Field(
        default_factory=list,
        description="Indices of the passages the answer actually relies on.",
    )
    answered: bool = Field(
        description="False when the passages do not contain the answer. Never guess to fill the gap.",
    )


@dataclass(frozen=True)
class Citation:
    """A passage the answer rests on, resolvable to a URL."""

    chunk_id: UUID
    document_id: UUID
    page: int
    snippet: str


@dataclass
class Answer:
    """A generated reply and everything needed to justify it."""

    text: str
    citations: List[Citation] = field(default_factory=list)
    answered: bool = True
    refusal_reason: Optional[str] = None
    disclaimer: Optional[str] = None
    generated: bool = True
