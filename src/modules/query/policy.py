"""Refusal policies applied before a query reaches the documents."""

import re
from typing import Optional, Sequence, Tuple

from .constants import (
    LEGAL_DISCLAIMER,
    LEGAL_PATTERNS,
    MEDICAL_DISCLAIMER,
    MEDICAL_PATTERNS,
    PII_PATTERNS,
    PII_REFUSAL,
)
from .schemas import PolicyAction, PolicyDecision


def _compile(patterns: Sequence[str]) -> Tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)


_PII = _compile(PII_PATTERNS)
_LEGAL = _compile(LEGAL_PATTERNS)
_MEDICAL = _compile(MEDICAL_PATTERNS)


def _matches(patterns: Tuple[re.Pattern[str], ...], query: str) -> bool:
    return any(pattern.search(query) for pattern in patterns)


def apply_policies(query: str) -> PolicyDecision:
    """Decide whether a query may be answered, and on what terms.

    Personal data is refused: the documents may genuinely contain it, and
    retrieval would surface it without hesitation. Legal and medical questions
    are answered with a disclaimer instead, because the underlying question is
    usually legitimate and refusing it outright is unhelpful.
    """
    if _matches(_PII, query):
        return PolicyDecision(action=PolicyAction.REFUSE, category="pii", message=PII_REFUSAL)

    if _matches(_LEGAL, query):
        return PolicyDecision(action=PolicyAction.DISCLAIM, category="legal", message=LEGAL_DISCLAIMER)

    if _matches(_MEDICAL, query):
        return PolicyDecision(action=PolicyAction.DISCLAIM, category="medical", message=MEDICAL_DISCLAIMER)

    return PolicyDecision(action=PolicyAction.ALLOW)


def disclaimer_for(decision: PolicyDecision) -> Optional[str]:
    """The text to prepend to an answer, when a policy asked for one."""
    return decision.message if decision.action is PolicyAction.DISCLAIM else None
