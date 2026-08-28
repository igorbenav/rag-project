"""MIME normalisation for upload validation.

Browsers, operating systems and HTTP clients emit different MIME strings for
the same format. Without normalisation an upload check rejects files whose
format is perfectly supported.
"""

MIME_SYNONYMS: dict[str, str] = {
    "application/x-pdf": "application/pdf",
    "application/acrobat": "application/pdf",
    "applications/vnd.pdf": "application/pdf",
    "text/pdf": "application/pdf",
    "text/x-pdf": "application/pdf",
}


def normalize_content_type(content_type: str) -> str:
    """Map client MIME variants to the canonical form used in allowlists."""
    return MIME_SYNONYMS.get(content_type.strip().lower().split(";")[0], content_type)
