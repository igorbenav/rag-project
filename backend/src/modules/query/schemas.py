"""Types describing what a query is and what should happen to it."""

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Intent(str, enum.Enum):
    """What the user is doing."""

    QUESTION = "question"
    GREETING = "greeting"
    GRATITUDE = "gratitude"
    CHITCHAT = "chitchat"
    ABOUT_THE_SYSTEM = "about_the_system"


class IntentClassification(BaseModel):
    """Schema the model fills in when the heuristics cannot decide."""

    intent: Intent = Field(description="What the user is doing.")
    reason: str = Field(max_length=200, description="One short sentence.")


@dataclass(frozen=True)
class IntentDecision:
    """The routing decision for one query."""

    intent: Intent
    needs_retrieval: bool
    decided_by: str
    reason: str


class QueryTransformation(BaseModel):
    """Schema the model fills in when rewriting a query for retrieval."""

    search_phrase: str = Field(
        max_length=300,
        description="The question restated as a dense, retrieval-friendly phrase.",
    )
    key_terms: List[str] = Field(
        default_factory=list,
        max_length=12,
        description="Exact terms, acronyms and expansions worth matching literally.",
    )


@dataclass(frozen=True)
class TransformedQuery:
    """One query, phrased for each retriever that will see it.

    The two retrievers want different things. An embedding is happiest with
    fluent natural language, so the dense side keeps close to what the user
    wrote. BM25 matches literal tokens, so the keyword side gets the acronyms
    and expansions the user did not type.
    """

    original: str
    dense_query: str
    keyword_query: str
    key_terms: List[str] = field(default_factory=list)
    transformed_by: str = "passthrough"

    @property
    def was_transformed(self) -> bool:
        return self.transformed_by != "passthrough"

    @classmethod
    def untransformed(cls, query: str) -> "TransformedQuery":
        return cls(original=query, dense_query=query, keyword_query=query)


class PolicyAction(str, enum.Enum):
    """What a policy says to do with a query."""

    ALLOW = "allow"
    REFUSE = "refuse"
    DISCLAIM = "disclaim"


@dataclass(frozen=True)
class PolicyDecision:
    """The outcome of the refusal policies."""

    action: PolicyAction
    category: Optional[str] = None
    message: Optional[str] = None

    @property
    def blocks_answer(self) -> bool:
        return self.action is PolicyAction.REFUSE


class CitationRead(BaseModel):
    """A passage the answer rests on. `chunk_id` resolves at /api/v1/chunks/{id}."""

    chunk_id: UUID
    document_id: UUID
    page: int
    snippet: str


class UnsupportedClaimRead(BaseModel):
    """A sentence of the answer that the passages did not carry."""

    sentence: str
    reason: str = ""


class CandidateRead(BaseModel):
    """One retrieved candidate and the rank each retriever gave it."""

    chunk_id: UUID
    document_id: UUID
    page: int
    fused_score: float
    dense_rank: Optional[int] = None
    keyword_rank: Optional[int] = None
    rerank_position: Optional[int] = None
    found_by: List[str] = Field(default_factory=list)


class TraceRead(BaseModel):
    """How the answer was reached, stage by stage."""

    intent: str
    intent_decided_by: str
    retrieved: bool
    dense_query: Optional[str] = None
    keyword_query: Optional[str] = None
    key_terms: List[str] = Field(default_factory=list)
    dense_count: int = 0
    keyword_count: int = 0
    fused_count: int = 0
    reranked: bool = False
    top_similarity: Optional[float] = None
    candidates: List[CandidateRead] = Field(default_factory=list)


class AnswerTableRead(BaseModel):
    """A comparison the client renders as a table."""

    columns: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)


class QueryCreate(BaseModel):
    """Body of `POST /collections/{collection_id}/queries`."""

    question: str = Field(min_length=1, max_length=2000, description="What to ask the documents.")


class QueryRead(BaseModel):
    """A question, its answer, and the evidence behind it."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    collection_id: UUID
    question: str
    answer: str
    answered: bool
    intent: str
    answer_list: List[str] = Field(default_factory=list)
    answer_table: Optional[AnswerTableRead] = None
    refusal_reason: Optional[str] = None
    disclaimer: Optional[str] = None
    citations: List[CitationRead] = Field(default_factory=list)
    unsupported_claims: List[UnsupportedClaimRead] = Field(default_factory=list)
    evidence_checked: bool = False
    trace: Optional[TraceRead] = None
    elapsed_seconds: float = 0.0
    created_at: datetime
    updated_at: Optional[datetime] = None

    @classmethod
    def from_model(cls, query: Any) -> "QueryRead":
        """Build from the stored row, whose citations and trace are JSON."""
        return cls(
            id=query.id,
            collection_id=query.collection_id,
            question=query.question,
            answer=query.answer,
            answered=query.answered,
            intent=query.intent,
            answer_list=query.answer_list or [],
            answer_table=AnswerTableRead(**query.answer_table) if query.answer_table else None,
            refusal_reason=query.refusal_reason,
            disclaimer=query.disclaimer,
            citations=[CitationRead(**citation) for citation in (query.citations or [])],
            unsupported_claims=[UnsupportedClaimRead(**claim) for claim in (query.unsupported_claims or [])],
            evidence_checked=query.evidence_checked,
            trace=TraceRead(**query.trace) if query.trace else None,
            elapsed_seconds=query.elapsed_seconds,
            created_at=query.created_at,
            updated_at=query.updated_at,
        )
