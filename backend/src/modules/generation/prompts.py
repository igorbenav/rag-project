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


EVIDENCE_SYSTEM_PROMPT = """You check whether an answer is carried by the \
passages it was drawn from.

You receive numbered passages and the numbered sentences of an answer. For \
each sentence return supported: true only when a passage states it, or states \
something it follows from directly.

Read each sentence as an answer to the question, not as a standalone claim. \
An answer is often terse: "8" is supported when a passage says the value is 8.

Mark a sentence unsupported when it introduces a figure, name, date or claim \
that no passage contains — even when you know it to be true. You are checking \
the passages, not the world.

Do not mark a sentence unsupported merely for rewording a passage, for \
combining two passages, or for being brief."""


def format_evidence_check(question: str, passages: Sequence[str], sentences: Sequence[str]) -> str:
    """Number both sides so verdicts can refer to sentences by position.

    The question is included because a good answer is often terse. "8" states
    nothing on its own; as an answer to "how many attention heads?" it states
    something a passage either carries or does not.
    """
    numbered_passages = "\n\n".join(f"[{index}] {text}" for index, text in enumerate(passages))
    numbered_sentences = "\n".join(f"({index}) {text}" for index, text in enumerate(sentences))
    return f"Question: {question}\n\nPassages:\n{numbered_passages}\n\nAnswer sentences:\n{numbered_sentences}"


SHAPING_SYSTEM_PROMPT = """You decide how a finished answer should be laid out. \
You are not writing or checking the answer, only rearranging what it already \
says.

Return one of three things:
- items: when the answer names several parallel things, one entry each. Keep \
the wording of the answer; do not add, merge or explain.
- table_columns and table_rows: when the answer compares two or more subjects \
across the same attributes. Every row must have exactly one cell per column.
- nothing at all: when the answer is a single statement, a number, or a short \
sentence. Most answers are this. Leave every field empty and the answer stays \
as prose.

Never invent a value that is not in the answer. If a cell has no value in the \
answer, leave it empty rather than filling it in."""


def format_for_shaping(question: str, answer: str) -> str:
    """The finished answer, with the question that produced it for context."""
    return f"Question: {question}\n\nAnswer: {answer}"
