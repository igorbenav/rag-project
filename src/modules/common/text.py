"""Text helpers shared across modules."""

import re
from typing import List

# Sentence end: terminator, optional closing quote or bracket, then whitespace.
# Over-splits on "et al." and "Fig. 3"; no abbreviation list can be complete.
_SENTENCE_END = re.compile(r"""(?<=[.!?])["\')\]]?\s+""")


def split_sentences(text: str) -> List[str]:
    """Split text on sentence boundaries, dropping empty fragments."""
    return [part.strip() for part in _SENTENCE_END.split(text.strip()) if part.strip()]
