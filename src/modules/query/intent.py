"""Deciding whether a query is worth searching the documents for.

Two layers. A short list of exact phrases catches the openers that are never
questions — "hello", "thanks" — for free and with no ambiguity. Everything else
goes to the model, because the alternative is a keyword heuristic that fails on
the first question phrased unusually.

The trade is latency against accuracy: the heuristic costs nothing and covers
the common case, the classification costs a round trip and covers the rest.
Running it concurrently with the query's own embedding hides that cost, since
neither depends on the other.
"""

import re

from ...infrastructure.logging import get_logger
from ...infrastructure.mistral import get_chat
from .constants import ABOUT_THE_SYSTEM, FAREWELLS, GRATITUDE, GREETINGS, RETRIEVING_INTENTS
from .prompts import CLASSIFIER_PROMPT
from .schemas import Intent, IntentClassification, IntentDecision

logger = get_logger(__name__)

_PUNCTUATION = re.compile(r"[^\w\s]")


def _normalise(query: str) -> str:
    return _PUNCTUATION.sub("", query.strip().lower()).strip()


def _from_phrase_list(query: str) -> IntentDecision | None:
    """Match the whole query against known openers, never a substring.

    Substring matching would classify "high availability" as a greeting.
    """
    normalised = _normalise(query)
    if not normalised:
        return None

    for phrases, intent in (
        (GREETINGS, Intent.GREETING),
        (GRATITUDE, Intent.GRATITUDE),
        (FAREWELLS, Intent.CHITCHAT),
        (ABOUT_THE_SYSTEM, Intent.ABOUT_THE_SYSTEM),
    ):
        if normalised in phrases:
            return IntentDecision(
                intent=intent,
                needs_retrieval=False,
                decided_by="phrase",
                reason=f"Exact match for a known {intent.value}.",
            )

    return None


async def detect_intent(query: str) -> IntentDecision:
    """Classify a query, and say whether it should reach the documents.

    Falls back to treating the query as a question if classification fails: a
    needless search is a smaller failure than refusing to answer a real one.
    """
    if not query.strip():
        return IntentDecision(
            intent=Intent.CHITCHAT,
            needs_retrieval=False,
            decided_by="phrase",
            reason="Empty query.",
        )

    matched = _from_phrase_list(query)
    if matched is not None:
        return matched

    try:
        classified = await get_chat().parse(query, IntentClassification, system=CLASSIFIER_PROMPT)
    except Exception as exc:  # noqa: BLE001 - fall back rather than fail the query
        logger.warning("Intent classification failed, assuming a question: %s", exc)
        return IntentDecision(
            intent=Intent.QUESTION,
            needs_retrieval=True,
            decided_by="fallback",
            reason="Classification unavailable.",
        )

    return IntentDecision(
        intent=classified.intent,
        needs_retrieval=classified.intent in RETRIEVING_INTENTS,
        decided_by="model",
        reason=classified.reason,
    )
