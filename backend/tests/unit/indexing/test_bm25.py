"""BM25 scoring. Pure arithmetic, so the expected values are computed by hand."""

import math
from uuid import UUID, uuid4

import pytest
from src.infrastructure.indexing.base import IndexedChunk
from src.infrastructure.indexing.constants import BM25_B, BM25_K1
from src.infrastructure.indexing.keyword.bm25 import BM25Index, tokenize

DOCUMENT = uuid4()


def chunk(content: str, page: int = 1, document_id: UUID = DOCUMENT) -> IndexedChunk:
    return IndexedChunk(chunk_id=uuid4(), document_id=document_id, page=page, content=content)


def index_of(*contents: str) -> BM25Index:
    index = BM25Index()
    index.add([chunk(content, page=number) for number, content in enumerate(contents, start=1)])
    return index


class TestTokenizer:
    def test_lowercases_and_splits_on_punctuation(self) -> None:
        assert tokenize("Multi-Head Attention!") == ["multi", "head", "attention"]

    def test_keeps_digits_because_vectors_handle_them_worst(self) -> None:
        assert tokenize("BERT-large has 340M params, masking 15%") == [
            "bert",
            "large",
            "has",
            "340m",
            "params",
            "masking",
            "15",
        ]

    def test_drops_single_characters(self) -> None:
        assert tokenize("a b to be") == ["to", "be"]

    @pytest.mark.parametrize("text", ["", "   ", "!!!", "a"])
    def test_yields_nothing_for_text_without_tokens(self, text: str) -> None:
        assert tokenize(text) == []


class TestScoring:
    def test_score_matches_the_bm25_formula(self) -> None:
        contents = [
            "the transformer uses multi head attention",
            "attention attention attention is repeated here",
            "a completely unrelated chunk about revenue and margins",
        ]
        index = index_of(*contents)

        hit = next(h for h in index.search("attention", k=3) if h.chunk.page == 1)

        total, document_frequency, term_frequency = 3, 2, 1
        idf = math.log(1 + (total - document_frequency + 0.5) / (document_frequency + 0.5))
        lengths = [len(tokenize(text)) for text in contents]
        average = sum(lengths) / len(lengths)
        expected = (
            idf * term_frequency * (BM25_K1 + 1) / (term_frequency + BM25_K1 * (1 - BM25_B + BM25_B * lengths[0] / average))
        )

        assert hit.score == pytest.approx(expected, abs=1e-9)

    def test_repeated_terms_saturate_rather_than_accumulate(self) -> None:
        index = index_of("attention once here", "attention attention attention here")

        scores = {hit.chunk.page: hit.score for hit in index.search("attention", k=2)}

        assert scores[2] > scores[1]
        assert scores[2] < 3 * scores[1], "three occurrences must not score three times one"

    def test_a_term_in_every_chunk_still_scores_positively(self) -> None:
        """The textbook idf goes negative past 50% document frequency."""
        index = index_of(*["common word here"] * 5)

        assert index._inverse_document_frequency("common") > 0

    def test_rarer_terms_outweigh_common_ones(self) -> None:
        index = index_of(
            "common term appears here alongside rare",
            "common term appears here",
            "common term appears here too",
        )

        hits = index.search("rare common", k=3)

        assert hits[0].chunk.page == 1, "the chunk with the rare term must rank first"

    def test_shorter_chunks_win_when_term_frequency_is_equal(self) -> None:
        index = index_of("attention", "attention " + "padding " * 40)

        hits = index.search("attention", k=2)

        assert hits[0].chunk.page == 1


class TestEmptyResults:
    def test_empty_index_returns_nothing(self) -> None:
        assert BM25Index().search("anything", k=5) == []

    def test_unknown_term_returns_nothing(self) -> None:
        assert index_of("alpha beta").search("gamma", k=5) == []

    @pytest.mark.parametrize("k", [0, -1])
    def test_non_positive_k_returns_nothing(self, k: int) -> None:
        assert index_of("alpha beta").search("alpha", k=k) == []


class TestMutation:
    def test_removing_a_document_drops_only_its_chunks(self) -> None:
        other = uuid4()
        index = BM25Index()
        index.add([chunk("attention here", 1), chunk("attention there", 2, document_id=other)])

        removed = index.remove_document(DOCUMENT)

        assert removed == 1
        assert index.stats().total_vectors == 1
        assert [hit.chunk.page for hit in index.search("attention", k=5)] == [2]

    def test_removing_an_absent_document_changes_nothing(self) -> None:
        index = index_of("attention here")

        assert index.remove_document(uuid4()) == 0
        assert index.stats().total_vectors == 1

    def test_scores_reflect_the_corpus_after_removal(self) -> None:
        """Removal rebuilds the postings; stale positions would mis-score."""
        other = uuid4()
        index = BM25Index()
        index.add([chunk("alpha", 1), chunk("alpha", 2), chunk("alpha beta", 3, document_id=other)])

        index.remove_document(DOCUMENT)
        hits = index.search("alpha", k=5)

        assert len(hits) == 1
        assert hits[0].chunk.page == 3

    def test_clear_empties_the_index(self) -> None:
        index = index_of("attention here")

        index.clear()

        assert index.stats().total_vectors == 0
        assert index.search("attention", k=5) == []
