"""Tuned values for PDF extraction and chunking."""

# Every PDF starts with this signature. Checked instead of the filename, which
# the client controls.
PDF_MAGIC = b"%PDF-"

# A page yielding fewer characters than this is treated as having no text,
# which in practice means a scan or a full-page figure. Set above a page
# number and running header (~20 chars) and below a sparse paragraph.
MIN_PAGE_CHARS = 50


# --- Chunking -------------------------------------------------------------
#
# Chunks are bounded in characters, not tokens: the boundary decisions below
# are all about text structure, and a token count would only be an estimate of
# the same thing. Roughly 4 characters per token for English prose.

# Target chunk size. Small chunks retrieve precisely — a 250-token span about
# one thing produces a focused embedding — but starve BM25 of the term
# statistics it needs and fragment answers that span a paragraph. Large chunks
# invert both. ~1000 characters keeps a chunk to a paragraph or two.
CHUNK_TARGET_CHARS = 1000

# Hard ceiling. A single sentence longer than this is split mid-sentence,
# because the alternative is an unbounded chunk.
CHUNK_MAX_CHARS = 1400

# Text repeated from the end of the previous chunk. Without it, a fact whose
# subject and object land either side of a boundary is retrievable by neither
# half. Costs ~20% more storage and embedding calls.
CHUNK_OVERLAP_CHARS = 200

# A trailing fragment shorter than this is merged into the previous chunk
# instead of standing alone. Isolated fragments ("References", a stray
# caption) match queries on their few words and crowd out real content.
MIN_CHUNK_CHARS = 120


# --- Upload limits --------------------------------------------------------

# Content types accepted for ingestion. application/octet-stream is included
# because curl and several browsers send it for a .pdf; the file signature is
# what actually decides, so the allowlist is a cheap first filter rather than
# the security boundary.
ALLOWED_UPLOAD_TYPES = {
    "application/pdf",
    "application/octet-stream",
}

# Per-file ceiling. Checked against the bytes actually read, never against the
# Content-Length header, which the client controls.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

# Files per request. Uploads are held in memory until the background task
# finishes, so this bounds the memory one request can pin.
MAX_UPLOAD_FILES = 20
