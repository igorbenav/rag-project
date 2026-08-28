"""Reciprocal rank fusion. Ranks in, ranks out — no scores involved."""

from typing import List
from uuid import uuid4

import pytest

from src.infrastructure.indexing.base import IndexedChunk, SearchHit
from src.modules.retrieval.fusion import reciprocal_rank_fusion

DOCUMENT = uuid4()
RRF_K = 60


def chunk(name: str) -> IndexedChunk:
    return IndexedChunk(chunk_id=uuid4(), document_id=DOCUMENT, page=1, content=name)


def hits(*pairs: tuple[IndexedChunk, float]) -> List[SearchHit]:
    return [SearchHit(chunk=c, score=s) for c, s in pairs]


def names(ranked) -> List[str]:
    return [entry.chunk.content for entry in ranked]


class TestFusedOrdering:
    def test_agreement_beats_a_single_retrievers_confidence(self) -> None:
        """The property RRF exists for, and the reason scores are discarded."""
        a, b = chunk("A"), chunk("B")

        fused = reciprocal_rank_fusion(
            dense=hits((a, 0.99), (b, 0.80)),
            keyword=hits((chunk("D"), 12.0), (b, 9.0)),
            rrf_k=RRF_K,
        )

        assert names(fused)[0] == "B", "second by both must beat first by one"

    def test_scores_match_the_rrf_formula(self) -> None:
        a, b = chunk("A"), chunk("B")

        fused = reciprocal_rank_fusion(hits((a, 0.9), (b, 0.8)), hits((b, 5.0)), rrf_k=RRF_K)
        by_name = {entry.chunk.content: entry.score for entry in fused}

        assert by_name["B"] == pytest.approx(1 / (RRF_K + 2) + 1 / (RRF_K + 1))
        assert by_name["A"] == pytest.approx(1 / (RRF_K + 1))

    def test_input_scores_do_not_influence_the_result(self) -> None:
        """BM25 is unbounded and cosine is not; only ranks may matter."""
        a, b = chunk("A"), chunk("B")

        modest = reciprocal_rank_fusion(hits((a, 0.51), (b, 0.50)), [], rrf_k=RRF_K)
        extreme = reciprocal_rank_fusion(hits((a, 999.0), (b, 0.01)), [], rrf_k=RRF_K)

        assert [entry.score for entry in modest] == [entry.score for entry in extreme]

    def test_a_larger_constant_flattens_the_advantage_of_rank_one(self) -> None:
        a, b = chunk("A"), chunk("B")
        pair = (hits((a, 0.9), (b, 0.8)), [])

        tight = reciprocal_rank_fusion(*pair, rrf_k=1)
        flat = reciprocal_rank_fusion(*pair, rrf_k=1000)

        assert tight[0].score / tight[1].score > flat[0].score / flat[1].score


class TestProvenance:
    def test_records_the_rank_and_score_from_each_retriever(self) -> None:
        shared = chunk("shared")

        fused = reciprocal_rank_fusion(hits((chunk("x"), 0.9), (shared, 0.7)), hits((shared, 8.0)), rrf_k=RRF_K)
        entry = next(e for e in fused if e.chunk.content == "shared")

        assert (entry.dense_rank, entry.keyword_rank) == (2, 1)
        assert (entry.dense_score, entry.keyword_score) == (0.7, 8.0)
        assert entry.found_by == ["dense", "keyword"]

    def test_reports_the_single_retriever_that_found_a_chunk(self) -> None:
        fused = reciprocal_rank_fusion(hits((chunk("only-dense"), 0.9)), [], rrf_k=RRF_K)

        assert fused[0].found_by == ["dense"]
        assert fused[0].keyword_rank is None


class TestDegenerateInput:
    def test_no_hits_at_all_yields_nothing(self) -> None:
        assert reciprocal_rank_fusion([], [], rrf_k=RRF_K) == []

    def test_one_empty_retriever_preserves_the_others_order(self) -> None:
        a, b, c = chunk("A"), chunk("B"), chunk("C")

        fused = reciprocal_rank_fusion(hits((a, 0.9), (b, 0.8), (c, 0.7)), [], rrf_k=RRF_K)

        assert names(fused) == ["A", "B", "C"]

    def test_disjoint_results_are_interleaved_by_rank(self) -> None:
        fused = reciprocal_rank_fusion(
            hits((chunk("d1"), 0.9), (chunk("d2"), 0.8)),
            hits((chunk("k1"), 9.0), (chunk("k2"), 8.0)),
            rrf_k=RRF_K,
        )

        assert set(names(fused)[:2]) == {"d1", "k1"}, "both rank-one chunks come first"
        assert len(fused) == 4

    def test_a_chunk_found_twice_by_one_retriever_is_not_double_counted(self) -> None:
        repeated = chunk("A")

        fused = reciprocal_rank_fusion(hits((repeated, 0.9)), hits((repeated, 9.0)), rrf_k=RRF_K)

        assert len(fused) == 1
