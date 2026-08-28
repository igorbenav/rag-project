"""Measure retrieval and refusal against the question set in questions.yaml.

Run inside the API container, which already has the database and the Mistral
key:

    docker compose exec web python eval/run.py
    docker compose exec web python eval/run.py --collection "ML papers"

Every configuration is a `RetrievalConfig`, so comparing strategies is a matter
of switching flags rather than editing the pipeline. Query embeddings are
computed once and reused across configurations: the point is to compare
retrieval, not to re-measure the embedding call four times.
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from uuid import UUID

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from src.infrastructure.database.session import local_session  # noqa: E402
from src.infrastructure.mistral import get_embedder  # noqa: E402
from src.modules.collection.models import Collection  # noqa: E402
from src.modules.document.models import Document  # noqa: E402
from src.modules.generation.service import GenerationService  # noqa: E402
from src.modules.query.intent import detect_intent  # noqa: E402
from src.modules.query.policy import apply_policies  # noqa: E402
from src.modules.query.schemas import PolicyAction  # noqa: E402
from src.modules.query.transform import transform_query  # noqa: E402
from src.modules.retrieval.config import RetrievalConfig  # noqa: E402
from src.modules.retrieval.service import RetrievalService  # noqa: E402

QUESTIONS = Path(__file__).parent / "questions.yaml"


@dataclass
class Question:
    """One evaluation case."""

    question: str
    document: Optional[str]
    pages: List[int]
    expect_refusal: bool = False
    note: str = ""

    @property
    def is_scorable(self) -> bool:
        """Only questions with a known answer location can score recall."""
        return bool(self.document and self.pages)


@dataclass
class RetrievalScore:
    """Retrieval quality for one configuration."""

    name: str
    hits_at_1: int = 0
    hits_at_5: int = 0
    reciprocal_ranks: List[float] = None  # type: ignore[assignment]
    total: int = 0

    def __post_init__(self) -> None:
        if self.reciprocal_ranks is None:
            self.reciprocal_ranks = []

    @property
    def mrr(self) -> float:
        return sum(self.reciprocal_ranks) / self.total if self.total else 0.0


def load_questions() -> List[Question]:
    rows = yaml.safe_load(QUESTIONS.read_text())
    return [Question(**row) for row in rows]


async def resolve_collection(name: Optional[str], db) -> Tuple[UUID, Dict[UUID, str]]:
    """Find the collection to evaluate, and map document ids to filenames."""
    statement = select(Collection.id, Collection.name).order_by(Collection.created_at.desc())
    if name:
        statement = statement.where(Collection.name == name)

    row = (await db.execute(statement.limit(1))).first()
    if row is None:
        raise SystemExit("No collection found. Ingest the sample PDFs first.")

    filenames = {
        document_id: filename
        for document_id, filename in (
            await db.execute(select(Document.id, Document.filename).where(Document.collection_id == row[0]))
        ).all()
    }
    if not filenames:
        raise SystemExit(f"Collection {row[1]!r} has no documents.")

    print(f"Collection: {row[1]}  ({len(filenames)} documents)\n")
    return row[0], filenames


def rank_of_expected(chunks: Sequence, question: Question, filenames: Dict[UUID, str]) -> Optional[int]:
    """1-based position of the first chunk on an expected page, if any."""
    for position, ranked in enumerate(chunks, start=1):
        filename = filenames.get(ranked.chunk.document_id, "")
        if question.document in filename and ranked.chunk.page in question.pages:
            return position
    return None


async def score_retrieval(
    collection_id: UUID,
    questions: Sequence[Question],
    embeddings: Dict[str, Tuple[str, List[float]]],
    config: RetrievalConfig,
    name: str,
    filenames: Dict[UUID, str],
    db,
) -> RetrievalScore:
    service = RetrievalService()
    score = RetrievalScore(name=name)

    for question in questions:
        keyword_query, embedding = embeddings[question.question]
        result = await service.retrieve(collection_id, keyword_query, embedding, config, db)

        score.total += 1
        rank = rank_of_expected(result.chunks, question, filenames)
        if rank is not None:
            score.hits_at_5 += 1
            score.hits_at_1 += rank == 1
            score.reciprocal_ranks.append(1.0 / rank)
        else:
            score.reciprocal_ranks.append(0.0)

    return score


async def score_refusals(
    collection_id: UUID, questions: Sequence[Question], config: RetrievalConfig, db
) -> Tuple[int, int, int, int]:
    """Run the full pipeline over refusal cases and answerable ones alike."""
    service, generation = RetrievalService(), GenerationService()
    embedder = get_embedder()

    should_refuse = [q for q in questions if q.expect_refusal]
    should_answer = [q for q in questions if q.is_scorable]

    refused_correctly = 0
    answered_correctly = 0

    for question in should_refuse + should_answer:
        policy = apply_policies(question.question)
        if policy.action is PolicyAction.REFUSE:
            answered = False
        else:
            intent = await detect_intent(question.question)
            if not intent.needs_retrieval:
                answered = False
            else:
                transformed = await transform_query(question.question)
                embedding = await embedder.embed_query(transformed.dense_query)
                result = await service.retrieve(collection_id, transformed.keyword_query, embedding, config, db)
                answer = await generation.answer(question.question, result, config.minimum_similarity, policy)
                answered = answer.answered

        if question.expect_refusal and not answered:
            refused_correctly += 1
        if question.is_scorable and answered:
            answered_correctly += 1

    return refused_correctly, len(should_refuse), answered_correctly, len(should_answer)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", help="Collection name. Defaults to the most recent.")
    parser.add_argument("--skip-answers", action="store_true", help="Retrieval metrics only.")
    args = parser.parse_args()

    questions = load_questions()
    scorable = [q for q in questions if q.is_scorable]
    print(
        f"{len(questions)} questions: {len(scorable)} scorable, {sum(q.expect_refusal for q in questions)} expected refusals\n"
    )

    async with local_session() as db:
        collection_id, filenames = await resolve_collection(args.collection, db)

        print("Embedding queries once, reused across configurations...")
        embedder = get_embedder()
        embeddings: Dict[str, Tuple[str, List[float]]] = {}
        for question in scorable:
            transformed = await transform_query(question.question)
            embeddings[question.question] = (
                transformed.keyword_query,
                await embedder.embed_query(transformed.dense_query),
            )

        base = RetrievalConfig.from_settings()
        ladder = [
            ("dense only", base.only_dense()),
            ("keyword only", base.only_keyword()),
            ("fused (RRF)", base.fused()),
            ("fused + rerank", base),
        ]

        print(f"\n{'configuration':<16} {'recall@1':>9} {'recall@5':>9} {'MRR':>7}")
        print("-" * 44)
        for name, config in ladder:
            score = await score_retrieval(collection_id, scorable, embeddings, config, name, filenames, db)
            print(
                f"{score.name:<16} {score.hits_at_1:>4}/{score.total:<4} "
                f"{score.hits_at_5:>4}/{score.total:<4} {score.mrr:>7.3f}"
            )

        if args.skip_answers:
            return

        print("\nrunning the full pipeline for refusal accuracy...")
        refused, refusable, answered, answerable = await score_refusals(collection_id, questions, base, db)
        print(f"\n  correct refusals   {refused}/{refusable}")
        print(f"  correct answers    {answered}/{answerable}")
        print(f"  false refusals     {answerable - answered}/{answerable}")


if __name__ == "__main__":
    asyncio.run(main())
