"""Tuned values for ranking."""

# Characters of each candidate shown to the reranker. Long enough to judge
# relevance, short enough that twenty candidates still fit in one prompt
# without the cost growing faster than the benefit.
RERANK_PASSAGE_CHARS = 1200
