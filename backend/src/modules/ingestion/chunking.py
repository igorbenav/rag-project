"""Splitting page text into chunks.

Chunks never cross a page boundary. Every answer this system produces cites a
page, and a chunk spanning pages 4 and 5 could only cite one of them.

Within a page the text is split on the strongest boundary that fits: paragraph
breaks first, then sentence ends, and only mid-sentence when a single sentence
exceeds the hard ceiling. Splitting on structure keeps a chunk about one thing,
which is what makes its embedding mean something.
"""

import re
from dataclasses import dataclass
from typing import Iterator, List

from ..common.text import split_sentences
from .constants import (
    CHUNK_MAX_CHARS,
    CHUNK_OVERLAP_CHARS,
    CHUNK_TARGET_CHARS,
    MIN_CHUNK_CHARS,
)
from .pdf import ExtractedPdf

_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")

_JOIN = "\n\n"


@dataclass(frozen=True)
class TextChunk:
    """A span of one page's text, ready to embed."""

    text: str
    page: int
    ordinal: int


def _split_oversized_sentence(sentence: str) -> List[str]:
    """Break a sentence with no usable boundary, preferring word gaps."""
    pieces: List[str] = []
    start = 0

    while start < len(sentence):
        end = min(start + CHUNK_MAX_CHARS, len(sentence))
        if end < len(sentence):
            word_gap = sentence.rfind(" ", start + MIN_CHUNK_CHARS, end)
            if word_gap != -1:
                end = word_gap
        pieces.append(sentence[start:end].strip())
        start = end

    return [piece for piece in pieces if piece]


def _structural_segments(page_text: str) -> Iterator[str]:
    """Yield the page as the smallest units worth keeping whole."""
    for paragraph in _PARAGRAPH_BREAK.split(page_text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        if len(paragraph) <= CHUNK_TARGET_CHARS:
            yield paragraph
            continue

        for sentence in split_sentences(paragraph):
            if len(sentence) <= CHUNK_MAX_CHARS:
                yield sentence
            else:
                yield from _split_oversized_sentence(sentence)


def _trailing_overlap(chunk_text: str) -> str:
    """The tail to repeat at the head of the next chunk, snapped to a word."""
    if len(chunk_text) <= CHUNK_OVERLAP_CHARS:
        return chunk_text

    tail = chunk_text[-CHUNK_OVERLAP_CHARS:]
    first_gap = tail.find(" ")
    return tail[first_gap + 1 :] if first_gap != -1 else tail


def _overlap_would_exceed_ceiling(overlap: str, segment: str) -> bool:
    return len(overlap) + len(segment) + 1 > CHUNK_MAX_CHARS


def _open_next_chunk(completed_chunk: str, segment: str) -> str:
    """Begin the next chunk, carrying overlap only when it still fits."""
    overlap = _trailing_overlap(completed_chunk)

    if not overlap or _overlap_would_exceed_ceiling(overlap, segment):
        return segment
    return f"{overlap} {segment}"


def _accumulate_chunk_texts(page_text: str) -> List[str]:
    """Grow chunks segment by segment, closing one when it reaches the target."""
    completed: List[str] = []
    open_chunk = ""

    for segment in _structural_segments(page_text):
        extended = f"{open_chunk}{_JOIN}{segment}" if open_chunk else segment

        if len(extended) <= CHUNK_TARGET_CHARS:
            open_chunk = extended
        elif open_chunk:
            completed.append(open_chunk)
            open_chunk = _open_next_chunk(open_chunk, segment)
        else:
            open_chunk = segment

    if open_chunk:
        completed.append(open_chunk)

    return completed


def _fold_trailing_orphan(chunk_texts: List[str]) -> List[str]:
    """Merge a final chunk too short to stand on its own into its predecessor."""
    if len(chunk_texts) < 2 or len(chunk_texts[-1]) >= MIN_CHUNK_CHARS:
        return chunk_texts

    *earlier, penultimate, orphan = chunk_texts
    return [*earlier, f"{penultimate}{_JOIN}{orphan}"]


def chunk_page(page_text: str, page_number: int, start_ordinal: int = 0) -> List[TextChunk]:
    """Split one page into chunks."""
    chunk_texts = _fold_trailing_orphan(_accumulate_chunk_texts(page_text))

    return [TextChunk(text=text, page=page_number, ordinal=start_ordinal + offset) for offset, text in enumerate(chunk_texts)]


def chunk_document(extracted: ExtractedPdf) -> List[TextChunk]:
    """Split every page of a document, numbering chunks across the whole file."""
    chunks: List[TextChunk] = []

    for page in extracted.pages:
        if page.text.strip():
            chunks.extend(chunk_page(page.text, page.number, start_ordinal=len(chunks)))

    return chunks
