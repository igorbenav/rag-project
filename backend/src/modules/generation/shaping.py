"""Giving a finished answer a shape a client can render.

Deliberately a second call. Adding these fields to the generation schema was
measured against mistral-medium and broke citation reporting: with a single
enum-typed field added, the same prompt and passages returned an empty `cited`
list while every other field stayed correct, and an uncited answer is refused.

Running afterwards removes the interaction entirely. The answer text and its
citations are already settled; this only decides how to lay them out, and a
failure here leaves the prose answer exactly as it was.
"""

from typing import List, Optional

from ...infrastructure.config.settings import get_settings
from ...infrastructure.logging import get_logger
from ...infrastructure.mistral import get_chat
from .prompts import SHAPING_SYSTEM_PROMPT, format_for_shaping
from .schemas import AnswerShape, AnswerTable

logger = get_logger(__name__)


async def shape_answer(question: str, answer: str) -> Optional[AnswerShape]:
    """Return a list or table form of the answer, or None to keep it as prose.

    The shape is inferred from which fields come back populated rather than
    from a format field the model has to keep consistent with them: a filled
    `table_columns` is a table, filled `items` is a list, neither is prose.
    """
    if not get_settings().ANSWER_SHAPING_ENABLED or not answer.strip():
        return None

    try:
        result = await get_chat().parse(
            format_for_shaping(question, answer),
            AnswerShape,
            system=SHAPING_SYSTEM_PROMPT,
            model=get_settings().MISTRAL_GENERATION_MODEL,
        )
    except Exception as exc:  # noqa: BLE001 - the prose answer is already valid
        logger.warning("Answer shaping failed, leaving the answer as prose: %s", exc)
        return None

    if result.table_columns and result.table_rows:
        if _rows_are_ragged(result.table_columns, result.table_rows):
            logger.debug("Discarding a table whose rows do not match its columns")
            return None
        return result

    return result if result.items else None


def _rows_are_ragged(columns: List[str], rows: List[List[str]]) -> bool:
    """A row with the wrong number of cells cannot be rendered."""
    return any(len(row) != len(columns) for row in rows)


def table_of(shape: AnswerShape) -> Optional[AnswerTable]:
    """The table form, when there is one."""
    if not shape.table_columns or not shape.table_rows:
        return None
    return AnswerTable(columns=shape.table_columns, rows=shape.table_rows)
