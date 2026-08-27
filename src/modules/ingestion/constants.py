"""Tuned values for PDF extraction and chunking."""

# Every PDF starts with this signature. Checked instead of the filename, which
# the client controls.
PDF_MAGIC = b"%PDF-"

# A page yielding fewer characters than this is treated as having no text,
# which in practice means a scan or a full-page figure. Set above a page
# number and running header (~20 chars) and below a sparse paragraph.
MIN_PAGE_CHARS = 50
