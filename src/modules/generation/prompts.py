"""Prompts and canned replies, selected by what the user is doing.

Only a question reaches the model. Greetings, thanks and questions about the
assistant are answered from fixed text: they need no documents, so spending a
round trip on them adds latency and a chance to hallucinate for no benefit.
"""

from typing import Sequence

from ..query.schemas import Intent

ANSWER_SYSTEM_PROMPT = """You answer questions using only the numbered passages \
provided. The passages come from documents the user uploaded.

Return:
- answer: the answer, in the fewest words that fully cover it. Plain prose, or \
a short list when the question asks for several things.
- cited: the indices of the passages the answer actually rests on. Cite what \
you used, not everything you were given.
- answered: false when the passages do not contain the answer.

Rules:
- Use only the passages. If they do not answer the question, set answered to \
false and leave answer empty. Do not fall back on what you already know.
- Never invent a figure, name, date or citation. A number that is not in the \
passages does not go in the answer.
- If the question names a specific model, system, company or person that the \
passages do not discuss, set answered to false. Passages about a similar thing \
are not about the thing that was asked for.
- Every answer must cite at least one passage. If you cannot point at the \
passage an answer came from, you do not have the answer.
- If the passages disagree, say so rather than choosing one silently.
- Do not describe the passages ("the provided text says"). Answer the question.
- Do not mention passage numbers in the answer text; that is what cited is for."""


GREETING_REPLY = "Hello. Ask me anything about the documents in this collection and I'll answer from them, with citations."

GRATITUDE_REPLY = "You're welcome. Ask another question whenever you like."

CHITCHAT_REPLY = "I'm here to answer questions about the documents in this collection. What would you like to know?"

INSUFFICIENT_EVIDENCE = (
    "I couldn't find enough evidence in the ingested documents to answer that. "
    "Try rephrasing, or upload a document that covers it."
)


def about_the_system_reply(document_count: int, filenames: Sequence[str]) -> str:
    """Describe what is actually in this collection, rather than in general."""
    if not document_count:
        return (
            "I answer questions about PDFs uploaded to this collection, citing "
            "the page each answer came from. Nothing has been ingested yet."
        )

    listed = ", ".join(filenames[:5])
    more = f", and {document_count - 5} more" if document_count > 5 else ""
    return (
        f"I answer questions about the {document_count} document(s) in this "
        f"collection ({listed}{more}), citing the page each answer came from."
    )


CANNED_REPLIES = {
    Intent.GREETING: GREETING_REPLY,
    Intent.GRATITUDE: GRATITUDE_REPLY,
    Intent.CHITCHAT: CHITCHAT_REPLY,
}


def format_passages(question: str, passages: Sequence[str]) -> str:
    """Number the passages so the model can cite them by position."""
    numbered = "\n\n".join(f"[{index}] {text}" for index, text in enumerate(passages))
    return f"Question: {question}\n\nPassages:\n{numbered}"
