"""Types describing what a query is and what should happen to it."""

import enum
from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field


class Intent(str, enum.Enum):
    """What the user is doing."""

    QUESTION = "question"
    GREETING = "greeting"
    GRATITUDE = "gratitude"
    CHITCHAT = "chitchat"
    ABOUT_THE_SYSTEM = "about_the_system"


#: Only a question is worth searching the documents for.
RETRIEVING_INTENTS = frozenset({Intent.QUESTION})


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
