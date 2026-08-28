"""Chunking is a pure function of the page text, so these need no fixtures."""

import pytest

from src.modules.ingestion.chunking import TextChunk, chunk_document, chunk_page
from src.modules.ingestion.constants import (
    CHUNK_MAX_CHARS,
    CHUNK_OVERLAP_CHARS,
    CHUNK_TARGET_CHARS,
    MIN_CHUNK_CHARS,
)
from src.modules.ingestion.pdf import ExtractedPdf, Page


def sentences(count: int, word: str = "alpha") -> str:
    """A paragraph of `count` roughly 60-character sentences."""
    return " ".join(f"{word} number {index} " + "filler " * 6 + "end." for index in range(count))


def words(text: str) -> set[str]:
    return {token for token in text.split() if token}


class TestSizeBounds:
    def test_no_chunk_exceeds_the_hard_ceiling(self) -> None:
        chunks = chunk_page(sentences(200), page_number=1)

        assert chunks
        assert all(len(chunk.text) <= CHUNK_MAX_CHARS for chunk in chunks)

    def test_a_sentence_longer_than_the_ceiling_is_split(self) -> None:
        one_long_sentence = "x" * (CHUNK_MAX_CHARS * 3)

        chunks = chunk_page(one_long_sentence, page_number=1)

        assert len(chunks) > 1
        assert all(len(chunk.text) <= CHUNK_MAX_CHARS for chunk in chunks)

    def test_overlap_is_dropped_rather_than_breaching_the_ceiling(self) -> None:
        """Regression: overlap used to be prepended without rechecking the bound."""
        page = f"{sentences(4)}\n\n" + "x" * (CHUNK_MAX_CHARS - 10) + ". tail."

        chunks = chunk_page(page, page_number=1)

        assert all(len(chunk.text) <= CHUNK_MAX_CHARS for chunk in chunks)

    def test_short_page_is_a_single_chunk(self) -> None:
        chunks = chunk_page("One short paragraph about attention.", page_number=1)

        assert len(chunks) == 1


class TestStructure:
    def test_paragraphs_under_the_target_are_kept_together(self) -> None:
        page = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."

        chunks = chunk_page(page, page_number=1)

        assert len(chunks) == 1
        assert "First" in chunks[0].text and "Third" in chunks[0].text

    def test_consecutive_chunks_overlap(self) -> None:
        chunks = chunk_page(sentences(60), page_number=1)

        assert len(chunks) > 1
        head_of_second = chunks[1].text[:CHUNK_OVERLAP_CHARS]
        assert any(word in chunks[0].text for word in head_of_second.split()[:5])

    def test_no_words_are_lost(self) -> None:
        page = sentences(80)

        chunks = chunk_page(page, page_number=1)

        assert words(page) <= words(" ".join(chunk.text for chunk in chunks))


class TestOrphans:
    def test_a_short_trailing_fragment_is_folded_into_its_predecessor(self) -> None:
        page = f"{sentences(40)}\n\nTiny."

        chunks = chunk_page(page, page_number=1)

        assert len(chunks) > 1
        assert all(len(chunk.text) >= MIN_CHUNK_CHARS for chunk in chunks)
        assert chunks[-1].text.endswith("Tiny.")

    def test_a_page_shorter_than_the_minimum_still_yields_one_chunk(self) -> None:
        chunks = chunk_page("Short.", page_number=1)

        assert [chunk.text for chunk in chunks] == ["Short."]


class TestEmptyInput:
    @pytest.mark.parametrize("page_text", ["", "   ", "\n\n\n", "\t \n"])
    def test_pages_without_text_yield_nothing(self, page_text: str) -> None:
        assert chunk_page(page_text, page_number=1) == []

    def test_single_word_page_survives(self) -> None:
        chunks = chunk_page("Transformer", page_number=1)

        assert [chunk.text for chunk in chunks] == ["Transformer"]


class TestPageAnchoring:
    def test_every_chunk_carries_the_page_it_came_from(self) -> None:
        document = ExtractedPdf(pages=[Page(number=1, text=sentences(40)), Page(number=2, text=sentences(40))])

        chunks = chunk_document(document)

        assert {chunk.page for chunk in chunks} == {1, 2}

    def test_no_chunk_mixes_text_from_two_pages(self) -> None:
        document = ExtractedPdf(
            pages=[
                Page(number=1, text=sentences(40, word="pagealpha")),
                Page(number=2, text=sentences(40, word="pagebeta")),
            ]
        )

        chunks = chunk_document(document)

        for chunk in chunks:
            foreign = "pagebeta" if chunk.page == 1 else "pagealpha"
            assert foreign not in chunk.text

    def test_ordinals_are_contiguous_across_the_whole_document(self) -> None:
        document = ExtractedPdf(pages=[Page(number=number, text=sentences(30)) for number in range(1, 4)])

        chunks = chunk_document(document)

        assert [chunk.ordinal for chunk in chunks] == list(range(len(chunks)))

    def test_pages_without_text_are_skipped_without_gaps_in_ordinals(self) -> None:
        document = ExtractedPdf(
            pages=[
                Page(number=1, text=sentences(20)),
                Page(number=2, text="   "),
                Page(number=3, text=sentences(20)),
            ]
        )

        chunks = chunk_document(document)

        assert 2 not in {chunk.page for chunk in chunks}
        assert [chunk.ordinal for chunk in chunks] == list(range(len(chunks)))


class TestChunkShape:
    def test_chunks_are_immutable(self) -> None:
        chunk = chunk_page("Some text about retrieval.", page_number=7)[0]

        assert isinstance(chunk, TextChunk)
        with pytest.raises(AttributeError):
            chunk.text = "mutated"  # type: ignore[misc]

    def test_target_is_below_the_ceiling(self) -> None:
        """The constants have to stay ordered for the algorithm to make sense."""
        assert MIN_CHUNK_CHARS < CHUNK_OVERLAP_CHARS < CHUNK_TARGET_CHARS < CHUNK_MAX_CHARS
