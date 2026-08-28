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


class SentenceVerdict(BaseModel):
    """Whether one sentence of an answer is carried by the passages."""

    index: int = Field(description="Position of the sentence in the answer, from 0.")
    supported: bool = Field(description="True only if a passage states or directly implies it.")
    reason: str = Field(default="", max_length=200)


class EvidenceCheck(BaseModel):
    """Schema the verifying model fills in."""

    verdicts: List[SentenceVerdict] = Field(default_factory=list)


@dataclass(frozen=True)
class UnsupportedClaim:
    """A sentence the passages did not carry."""

    sentence: str
    reason: str


class AnswerShape(BaseModel):
    """How a finished answer should be laid out, decided in a separate call.

    No format field: the shape is whichever collection comes back populated,
    so there is no second value that can disagree with the data.
    """

    items: List[str] = Field(
        default_factory=list,
        description="One entry per thing the answer lists. Empty unless the answer is a list.",
    )
    table_columns: List[str] = Field(
        default_factory=list, description="Column headers. Empty unless the answer is a comparison."
    )
    table_rows: List[List[str]] = Field(default_factory=list, description="One list of cells per row, matching table_columns.")


@dataclass(frozen=True)
class AnswerTable:
    """A comparison, as columns and rows rather than formatted text."""

    columns: List[str]
    rows: List[List[str]]


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
    list_items: List[str] = field(default_factory=list)
    table: Optional["AnswerTable"] = None
    citations: List[Citation] = field(default_factory=list)
    answered: bool = True
    refusal_reason: Optional[str] = None
    disclaimer: Optional[str] = None
    generated: bool = True
    unsupported_claims: List["UnsupportedClaim"] = field(default_factory=list)
    evidence_checked: bool = False
