"""Tuned values for answer generation."""

# Characters of a passage returned alongside a citation. Enough to recognise
# the source in a UI without repeating the chunk, which is one request away at
# /chunks/{id}.
CITATION_SNIPPET_CHARS = 300

# Sentences an answer may contain before the evidence check gives up on
# splitting it usefully. Answers here are typically one or two sentences; a
# long one is prose the check cannot verify claim by claim anyway.
MAX_SENTENCES_TO_CHECK = 12
