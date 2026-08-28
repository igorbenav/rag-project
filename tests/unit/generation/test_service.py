"""Generation guards: what stops a hallucination reaching the user.

The model is stubbed. These assert what the service does with a response, not
what a model produces — the guards must hold whatever comes back.
"""

from typing import Any
from uuid import uuid4

import pytest

from src.infrastructure.indexing.base import IndexedChunk
from src.modules.generation.schemas import GeneratedAnswer
from src.modules.generation.service import GenerationService
from src.modules.query.schemas import Intent, PolicyAction, PolicyDecision
from src.modules.retrieval.schemas import RankedChunk, RetrievalResult

DOCUMENT = uuid4()


def result(*contents: str, similarity: float = 0.9) -> RetrievalResult:
    chunks = [
        RankedChunk(
            chunk=IndexedChunk(chunk_id=uuid4(), document_id=DOCUMENT, page=page, content=content),
            score=0.03,
            dense_score=similarity,
        )
        for page, content in enumerate(contents, start=1)
    ]
    return RetrievalResult(chunks=chunks, top_similarity=similarity if chunks else None)


def stub_model(monkeypatch: pytest.MonkeyPatch, answer: GeneratedAnswer, *, verdicts: Any = None) -> None:
    """Stub both the answering call and the evidence check."""

    class Stub:
        async def parse(self, _prompt: str, schema: type, **_: object) -> Any:
            if schema is GeneratedAnswer:
                return answer
            return verdicts if verdicts is not None else schema(verdicts=[])

    monkeypatch.setattr("src.modules.generation.service.get_chat", lambda: Stub())
    monkeypatch.setattr("src.modules.generation.evidence.get_chat", lambda: Stub())


class TestCitationGuard:
    async def test_an_answer_citing_nothing_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The exact failure seen live: mistral-small answered "12" with no citation."""
        stub_model(monkeypatch, GeneratedAnswer(answer="12", cited=[], answered=True))

        answer = await GenerationService().answer("how many heads?", result("h = 8"), 0.0)

        assert answer.answered is False
        assert answer.refusal_reason == "answer_without_citation"

    async def test_citations_resolve_to_the_chunks_they_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stub_model(monkeypatch, GeneratedAnswer(answer="8 heads.", cited=[1], answered=True))
        retrieval = result("first passage", "h = 8 parallel attention layers")

        answer = await GenerationService().answer("how many heads?", retrieval, 0.0)

        assert [citation.page for citation in answer.citations] == [2]
        assert answer.citations[0].chunk_id == retrieval.chunks[1].chunk.chunk_id

    async def test_indices_outside_the_passage_list_are_dropped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stub_model(monkeypatch, GeneratedAnswer(answer="8 heads.", cited=[0, 99, -1], answered=True))

        answer = await GenerationService().answer("q", result("h = 8"), 0.0)

        assert len(answer.citations) == 1


class TestRefusal:
    async def test_nothing_retrieved_means_nothing_to_answer_from(self) -> None:
        answer = await GenerationService().answer("q", RetrievalResult(), 0.0)

        assert answer.answered is False
        assert answer.refusal_reason == "no_results"

    async def test_similarity_below_the_threshold_refuses_before_calling_the_model(self) -> None:
        answer = await GenerationService().answer("q", result("text", similarity=0.4), 0.7)

        assert answer.answered is False
        assert answer.refusal_reason == "below_similarity_threshold"

    async def test_a_threshold_of_zero_disables_the_check(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stub_model(monkeypatch, GeneratedAnswer(answer="answer", cited=[0], answered=True))

        answer = await GenerationService().answer("q", result("text", similarity=0.1), 0.0)

        assert answer.answered is True

    async def test_the_model_reporting_no_answer_is_honoured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stub_model(monkeypatch, GeneratedAnswer(answer="", cited=[], answered=False))

        answer = await GenerationService().answer("q", result("unrelated"), 0.0)

        assert answer.refusal_reason == "model_found_no_answer"

    async def test_a_generation_failure_becomes_a_refusal_not_an_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class Broken:
            async def parse(self, *args: object, **kwargs: object) -> object:
                raise RuntimeError("mistral down")

        monkeypatch.setattr("src.modules.generation.service.get_chat", lambda: Broken())

        answer = await GenerationService().answer("q", result("text"), 0.0)

        assert answer.answered is False
        assert answer.refusal_reason == "generation_failed"


class TestDisclaimers:
    async def test_a_disclaim_policy_rides_along_with_the_answer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The live corpus never produced an answerable legal question."""
        stub_model(monkeypatch, GeneratedAnswer(answer="The contract runs to 2030.", cited=[0], answered=True))
        policy = PolicyDecision(action=PolicyAction.DISCLAIM, category="legal", message="Not legal advice.")

        answer = await GenerationService().answer("q", result("term ends 2030"), 0.0, policy)

        assert answer.answered is True
        assert answer.disclaimer == "Not legal advice."

    async def test_an_allow_policy_attaches_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stub_model(monkeypatch, GeneratedAnswer(answer="answer", cited=[0], answered=True))

        answer = await GenerationService().answer("q", result("text"), 0.0, PolicyDecision(action=PolicyAction.ALLOW))

        assert answer.disclaimer is None


class TestRepliesWithoutRetrieval:
    @pytest.mark.parametrize("intent", [Intent.GREETING, Intent.GRATITUDE, Intent.CHITCHAT])
    def test_conversational_intents_answer_without_the_model(self, intent: Intent) -> None:
        answer = GenerationService().reply_without_retrieval(intent, 3, ["a.pdf"])

        assert answer.text
        assert answer.generated is False

    def test_asking_about_the_system_names_the_actual_documents(self) -> None:
        answer = GenerationService().reply_without_retrieval(Intent.ABOUT_THE_SYSTEM, 2, ["bert.pdf", "attention.pdf"])

        assert "bert.pdf" in answer.text
        assert "2 document" in answer.text

    def test_an_empty_collection_says_so(self) -> None:
        answer = GenerationService().reply_without_retrieval(Intent.ABOUT_THE_SYSTEM, 0, [])

        assert "nothing has been ingested" in answer.text.lower()
