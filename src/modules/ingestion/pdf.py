"""Text extraction from PDFs, one page at a time.

Page numbers survive extraction because every citation the system produces
names a page, and the only place that information exists is here.
"""

import asyncio
import re
from dataclasses import dataclass
from io import BytesIO
from typing import List

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from ...infrastructure.logging import get_logger
from ..common.exceptions import UnsupportedMediaTypeError, ValidationError
from .constants import MIN_PAGE_CHARS, PDF_MAGIC

logger = get_logger(__name__)

_HYPHEN_LINEBREAK = re.compile(r"(\w)-\n(\w)")
_TRAILING_SPACES = re.compile(r"[ \t]+\n")
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")


@dataclass(frozen=True)
class Page:
    """One page of extracted text. `number` is 1-based, as printed."""

    number: int
    text: str


@dataclass(frozen=True)
class ExtractedPdf:
    """The text of a PDF, page by page."""

    pages: List[Page]

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def pages_with_text(self) -> List[Page]:
        return [page for page in self.pages if len(page.text) >= MIN_PAGE_CHARS]

    @property
    def is_probably_scanned(self) -> bool:
        """True when most pages yielded no text.

        A born-digital PDF gives up its text directly; a scan gives nothing and
        would need OCR. Recorded so the failure is legible rather than looking
        like an empty document.
        """
        if not self.pages:
            return True
        return len(self.pages_with_text) < len(self.pages) / 2


def looks_like_pdf(data: bytes) -> bool:
    """Check the file signature rather than trusting the filename."""
    return data.startswith(PDF_MAGIC)


def _normalise(text: str) -> str:
    """Undo the artefacts of PDF layout that would otherwise reach the index.

    Words hyphenated across a line break are rejoined: left alone, "trans-
    former" is two tokens that match neither "transformer" nor each other.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _HYPHEN_LINEBREAK.sub(r"\1\2", text)
    text = _TRAILING_SPACES.sub("\n", text)
    text = _EXCESS_BLANK_LINES.sub("\n\n", text)
    return text.strip()


def _extract_sync(data: bytes) -> ExtractedPdf:
    """Read every page. Runs in a worker thread; pypdf is synchronous."""
    try:
        reader = PdfReader(BytesIO(data))
    except PdfReadError as exc:
        raise ValidationError(f"Could not read PDF: {exc}") from exc

    if reader.is_encrypted:
        try:
            if reader.decrypt("") == 0:
                raise ValidationError("PDF is password protected")
        except (NotImplementedError, PdfReadError) as exc:
            raise ValidationError(f"PDF is encrypted and could not be opened: {exc}") from exc

    pages: List[Page] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            raw = page.extract_text() or ""
        except Exception as exc:
            logger.warning("Page %d could not be extracted: %s", index, exc)
            raw = ""
        pages.append(Page(number=index, text=_normalise(raw)))

    if not pages:
        raise ValidationError("PDF contains no pages")

    return ExtractedPdf(pages=pages)


async def extract_pdf(data: bytes) -> ExtractedPdf:
    """Extract text from PDF bytes.

    Raises:
        UnsupportedMediaTypeError: if the bytes are not a PDF.
        ValidationError: if the PDF is unreadable, encrypted, or empty.
    """
    if not looks_like_pdf(data):
        raise UnsupportedMediaTypeError("Only PDF files can be ingested")

    return await asyncio.to_thread(_extract_sync, data)
