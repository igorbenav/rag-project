"""Re-reading an answer against the passages it was supposed to come from.

Generation is instructed to use only the passages, and mostly does. This reads
the finished answer back and asks, sentence by sentence, whether the passages
actually carry it — a second opinion from a model that has not just spent its
attention composing the text.

It catches a specific failure: an answer that is largely grounded but slips in
one figure or name from the model's own memory. Requiring a citation catches an
answer with no support at all; this catches the sentence inside a supported
answer that nothing backs.
"""

from typing import List, Sequence

from ...infrastructure.config.settings import get_settings
from ...infrastructure.logging import get_logger
from ...infrastructure.mistral import get_chat
from ..common.text import split_sentences as _split
from .constants import MAX_SENTENCES_TO_CHECK
from .prompts import EVIDENCE_SYSTEM_PROMPT, format_evidence_check
from .schemas import EvidenceCheck, UnsupportedClaim

logger = get_logger(__name__)


def split_sentences(answer: str) -> List[str]:
    """Split an answer into the units the check judges.

    Answers here are short, so a list item or a bare value counts as a
    sentence: "8" is a claim that either the passages carry or they do not.
    """
    return _split(answer)[:MAX_SENTENCES_TO_CHECK]


async def check_evidence(answer: str, passages: Sequence[str]) -> List[UnsupportedClaim]:
    """Return the sentences the passages do not support.

    An empty list means either that everything checked out or that the check
    could not run; callers read `Answer.evidence_checked` to tell those apart.
    """
    sentences = split_sentences(answer)
    if not sentences or not passages:
        return []

    try:
        result = await get_chat().parse(
            format_evidence_check(passages, sentences),
            EvidenceCheck,
            system=EVIDENCE_SYSTEM_PROMPT,
            model=get_settings().MISTRAL_GENERATION_MODEL,
        )
    except Exception as exc:  # noqa: BLE001 - a failed check must not fail the answer
        logger.warning("Evidence check failed: %s", exc)
        return []

    return [
        UnsupportedClaim(sentence=sentences[verdict.index], reason=verdict.reason)
        for verdict in result.verdicts
        if not verdict.supported and 0 <= verdict.index < len(sentences)
    ]
