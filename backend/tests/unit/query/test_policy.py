"""Refusal policies. Pure pattern matching, so no fixtures are needed."""

import pytest
from src.modules.query.policy import apply_policies, disclaimer_for
from src.modules.query.schemas import PolicyAction


class TestPersonalData:
    @pytest.mark.parametrize(
        "query",
        [
            "What is John Smith's social security number?",
            "Give me his home address",
            "What is the phone number for the CFO?",
            "Find the bank account details in the filing",
            "What is the passport number of the applicant?",
        ],
    )
    def test_requests_for_identifying_details_are_refused(self, query: str) -> None:
        decision = apply_policies(query)

        assert decision.action is PolicyAction.REFUSE
        assert decision.category == "pii"
        assert decision.blocks_answer is True

    def test_the_refusal_explains_itself(self) -> None:
        assert "personal" in (apply_policies("give me his home address").message or "").lower()


class TestDisclaimers:
    @pytest.mark.parametrize(
        "query,category",
        [
            ("Should I sue them over this contract?", "legal"),
            ("Is this agreement legally binding?", "legal"),
            ("Am I liable for the shortfall?", "legal"),
            ("Should I take this medication daily?", "medical"),
            ("Do I have diabetes based on these numbers?", "medical"),
        ],
    )
    def test_advice_seeking_questions_are_answered_with_a_caveat(self, query: str, category: str) -> None:
        """Refusing outright is unhelpful; the underlying question is legitimate."""
        decision = apply_policies(query)

        assert decision.action is PolicyAction.DISCLAIM
        assert decision.category == category
        assert decision.blocks_answer is False
        assert disclaimer_for(decision)

    def test_a_disclaimer_says_it_is_not_advice(self) -> None:
        assert "not legal advice" in (apply_policies("should i sue them?").message or "")


class TestOrdinaryQuestions:
    @pytest.mark.parametrize(
        "query",
        [
            "How many attention heads does the base Transformer use?",
            "What was the operating margin in 2024?",
            "Summarise the results section",
            "Is this the legal filing that mentions attention heads?",
        ],
    )
    def test_pass_through_untouched(self, query: str) -> None:
        decision = apply_policies(query)

        assert decision.action is PolicyAction.ALLOW
        assert disclaimer_for(decision) is None
