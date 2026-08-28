"""Tuned values for the indexes."""

# BM25 term-frequency saturation. Higher means repeated terms keep adding
# weight; lower means the second occurrence already counts for little. 1.2 is
# the value Lucene and the original TREC experiments settled on.
BM25_K1 = 1.2

# BM25 length normalisation, from 0 (ignore document length) to 1 (fully
# normalise). At 0.75 a long chunk is penalised for its length but not erased,
# which suits chunks that are deliberately near-uniform in size.
BM25_B = 0.75

# Single characters carry no retrieval signal and inflate the postings.
MIN_TOKEN_LENGTH = 2
