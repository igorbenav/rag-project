"""Rewriting a query so each retriever gets the form it handles best.

A user's question is written for a person, not for a search index. It carries
filler the embedding has to absorb, and it omits the acronyms and exact terms a
keyword index needs — someone asking "how does it search the index at inference
time" will never type MIPS, which is the token the paper actually uses.

So one model call produces two things: a compact restatement for the dense
side, and a set of literal terms appended to the keyword side. Failure is
non-fatal; the original query is a perfectly usable query.
"""

from ...infrastructure.logging import get_logger
from ...infrastructure.mistral import get_chat
from .prompts import TRANSFORM_PROMPT
from .schemas import QueryTransformation, TransformedQuery

logger = get_logger(__name__)

def _keyword_query(search_phrase: str, key_terms: list[str]) -> str:
    """Join the phrase with its expansions.

    Repetition is harmless: BM25 saturates term frequency, so a term appearing
    twice in the query is not counted twice.
    """
    return " ".join([search_phrase, *key_terms])


async def transform_query(query: str) -> TransformedQuery:
    """Produce retriever-specific phrasings of a query.

    Returns the query unchanged if the model call fails, which costs recall on
    that query rather than failing it.
    """
    if not query.strip():
        return TransformedQuery.untransformed(query)

    try:
        result = await get_chat().parse(query, QueryTransformation, system=TRANSFORM_PROMPT)
    except Exception as exc:  # noqa: BLE001 - degrade to the original query
        logger.warning("Query transformation failed, using the original: %s", exc)
        return TransformedQuery.untransformed(query)

    search_phrase = result.search_phrase.strip() or query

    return TransformedQuery(
        original=query,
        dense_query=search_phrase,
        keyword_query=_keyword_query(search_phrase, result.key_terms),
        key_terms=result.key_terms,
        sub_questions=result.sub_questions,
        transformed_by="model",
    )
