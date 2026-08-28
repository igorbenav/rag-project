"""Tuned values for answer generation."""

# Characters of a passage returned alongside a citation. Enough to recognise
# the source in a UI without repeating the chunk, which is one request away at
# /chunks/{id}.
CITATION_SNIPPET_CHARS = 300
