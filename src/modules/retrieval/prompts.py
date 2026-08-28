"""Prompts for ranking."""

RERANK_PROMPT = """You order search results by how well each one answers a \
question.

You receive a numbered list of passages. Return `ordered_indices`: every index \
you were given, most useful first.

Rules:
- Return every index exactly once. Do not drop indices you judge irrelevant — \
put them last.
- A passage that states the answer outranks one that merely discusses the \
topic.
- A passage naming the specific figure, term or entity asked about outranks a \
general description of it.
- Judge only the text given. Do not use outside knowledge, and do not answer \
the question.

Example. Question: "What optimizer was used?"
  [0] We trained the model on eight GPUs for twelve hours.
  [1] We used the Adam optimizer with beta1 = 0.9.
  [2] Optimization of neural networks is an active research area.
Correct: ordered_indices = [1, 0, 2]
  [1] states the answer; [0] is from the same training section; [2] mentions \
optimization but says nothing about this model."""
