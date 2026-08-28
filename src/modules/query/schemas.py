"""Types describing what a query is and what should happen to it."""

import enum
from dataclasses import dataclass, field
from typing import List, Optional

from pydantic import BaseModel, Field


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
    sub_questions: List[str] = Field(
        default_factory=list,
        max_length=4,
        description="Only for genuinely multi-part questions; otherwise empty.",
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
    sub_questions: List[str] = field(default_factory=list)
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
