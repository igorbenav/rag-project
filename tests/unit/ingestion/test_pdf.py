"""Extraction: the pure text-cleaning helpers, plus real PDFs from samples/."""

from pathlib import Path

import pytest

from src.modules.common.exceptions import UnsupportedMediaTypeError, ValidationError
from src.modules.ingestion.constants import MIN_PAGE_CHARS
from src.modules.ingestion.pdf import (
    ExtractedPdf,
    Page,
    _clean_page_text,
    extract_pdf,
    looks_like_pdf,
)

SAMPLE = Path("samples/attention-is-all-you-need.pdf")


class TestFileTypeDetection:
    def test_accepts_the_pdf_signature(self) -> None:
        assert looks_like_pdf(b"%PDF-1.7\n...")

    @pytest.mark.parametrize("data", [b"", b"plain text", b"PK\x03\x04zip", b"\x89PNG\r\n"])
    def test_rejects_anything_else(self, data: bytes) -> None:
        assert not looks_like_pdf(data)

    def test_signature_is_checked_not_the_filename(self) -> None:
        """A .pdf name on non-PDF bytes must still be rejected."""
        assert not looks_like_pdf(b"<html>not really a pdf</html>")


class TestTextCleaning:
    def test_rejoins_words_broken_across_lines(self) -> None:
        assert _clean_page_text("trans-\nformer") == "transformer"

    def test_leaves_a_genuine_trailing_dash_alone(self) -> None:
        assert "-" in _clean_page_text("see Figure 1 -\n\nnext section")

    def test_normalises_carriage_returns(self) -> None:
        assert "\r" not in _clean_page_text("first\r\nsecond\rthird")

    def test_collapses_runs_of_blank_lines(self) -> None:
        assert _clean_page_text("first\n\n\n\n\nsecond") == "first\n\nsecond"

    def test_strips_trailing_spaces_before_newlines(self) -> None:
        assert _clean_page_text("first   \nsecond") == "first\nsecond"


class TestExtractedPdf:
    def test_counts_only_pages_carrying_text(self) -> None:
        document = ExtractedPdf(pages=[Page(number=1, text="x" * MIN_PAGE_CHARS), Page(number=2, text="short")])

        assert document.page_count == 2
        assert [page.number for page in document.pages_with_text] == [1]

    def test_a_document_of_empty_pages_reads_as_scanned(self) -> None:
        document = ExtractedPdf(pages=[Page(number=n, text="") for n in range(1, 4)])

        assert document.is_probably_scanned

    def test_a_document_of_full_pages_does_not(self) -> None:
        document = ExtractedPdf(pages=[Page(number=n, text="x" * (MIN_PAGE_CHARS + 1)) for n in range(1, 4)])

        assert not document.is_probably_scanned


class TestRejection:
    async def test_non_pdf_bytes_are_unsupported_media(self) -> None:
        with pytest.raises(UnsupportedMediaTypeError):
            await extract_pdf(b"just some text")

    async def test_a_truncated_pdf_is_a_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            await extract_pdf(b"%PDF-1.5\ntruncated right here")


@pytest.mark.skipif(not SAMPLE.exists(), reason="sample PDF not present")
class TestRealDocument:
    async def test_extracts_every_page_with_one_based_numbering(self) -> None:
        document = await extract_pdf(SAMPLE.read_bytes())

        assert document.page_count == 15
        assert [page.number for page in document.pages] == list(range(1, 16))

    async def test_every_page_of_a_born_digital_pdf_has_text(self) -> None:
        document = await extract_pdf(SAMPLE.read_bytes())

        assert len(document.pages_with_text) == document.page_count
        assert not document.is_probably_scanned

    async def test_hyphenated_words_do_not_survive_extraction(self) -> None:
        document = await extract_pdf(SAMPLE.read_bytes())

        joined = "\n".join(page.text for page in document.pages)
        assert "self-\nattention" not in joined
