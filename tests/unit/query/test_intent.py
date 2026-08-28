"""Routing: which queries reach the documents, and which never should."""

import pytest

from src.modules.query.intent import detect_intent, quick_intent
from src.modules.query.schemas import Intent


class TestPhraseMatching:
    @pytest.mark.parametrize(
        "query,intent",
        [
            ("hello", Intent.GREETING),
            ("Hi!", Intent.GREETING),
            ("good morning", Intent.GREETING),
            ("thanks", Intent.GRATITUDE),
            ("Thank you.", Intent.GRATITUDE),
            ("that was helpful", Intent.GRATITUDE),
            ("bye", Intent.CHITCHAT),
            ("what can you do?", Intent.ABOUT_THE_SYSTEM),
        ],
    )
    def test_known_openers_resolve_without_a_model_call(self, query: str, intent: Intent) -> None:
        decision = quick_intent(query)

        assert decision is not None
        assert decision.intent is intent
        assert decision.needs_retrieval is False
        assert decision.decided_by == "phrase"

    @pytest.mark.parametrize(
        "query",
        [
            "high availability setup",
            "thanks to the residual connections, what happens to the gradient?",
            "hello world program in the appendix",
            "how many heads does it use?",
        ],
    )
    def test_phrases_match_the_whole_query_never_a_substring(self, query: str) -> None:
        """'hi' inside 'high' would silently discard a real question."""
        assert quick_intent(query) is None

    def test_punctuation_and_case_do_not_defeat_the_match(self) -> None:
        assert quick_intent("  HELLO!!  ") is not None


class TestFallback:
    async def test_an_empty_query_never_retrieves(self) -> None:
        decision = await detect_intent("   ")

        assert decision.needs_retrieval is False
        assert decision.decided_by == "phrase"

    async def test_a_classifier_failure_assumes_a_question(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A needless search is a smaller failure than refusing a real question."""

        class Broken:
            async def parse(self, *args: object, **kwargs: object) -> object:
                raise RuntimeError("mistral unavailable")

        monkeypatch.setattr("src.modules.query.intent.get_chat", lambda: Broken())

        decision = await detect_intent("what optimizer was used?")

        assert decision.needs_retrieval is True
        assert decision.decided_by == "fallback"
