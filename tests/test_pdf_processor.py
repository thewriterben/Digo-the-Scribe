"""Tests for the PDF processor / ResourceLibrary."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from digo.pdf_processor import DocumentChunk, IndexedDocument, ResourceLibrary

# ---------------------------------------------------------------------------
# DocumentChunk
# ---------------------------------------------------------------------------


class TestDocumentChunk:
    def test_reference_format(self):
        chunk = DocumentChunk(
            source="Battle Plan",
            file_path="/tmp/battle_plan.pdf",
            page_number=7,
            text="Phase 1: Fund launch strategy.",
        )
        assert chunk.reference == "Battle Plan, page 7"


# ---------------------------------------------------------------------------
# IndexedDocument (with mocked pdfplumber)
# ---------------------------------------------------------------------------


class TestIndexedDocument:
    def _mock_pdf(self, pages_text: list[str]):
        """Return a mock pdfplumber PDF context manager with given page texts."""
        mock_pages = []
        for text in pages_text:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = text
            mock_pages.append(mock_page)
        mock_pdf = MagicMock()
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        mock_pdf.pages = mock_pages
        return mock_pdf

    def test_load_extracts_pages(self, tmp_path: Path):
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF fake content")

        pages = ["Page one text about Battle Plan.", "Page two about crypto fund."]
        with patch("digo.pdf_processor.pdfplumber.open", return_value=self._mock_pdf(pages)):
            doc = IndexedDocument.from_pdf("Test Doc", pdf_path)

        assert len(doc.chunks) == 2
        assert doc.chunks[0].page_number == 1
        assert doc.chunks[1].page_number == 2

    def test_search_returns_relevant_chunks(self, tmp_path: Path):
        pdf_path = tmp_path / "bp.pdf"
        pdf_path.write_bytes(b"%PDF fake")

        pages = [
            "The crypto fund launch requires thorough planning.",
            "Marketing strategy for the coin is outlined here.",
            "Technical blockchain integration details follow.",
        ]
        with patch("digo.pdf_processor.pdfplumber.open", return_value=self._mock_pdf(pages)):
            doc = IndexedDocument.from_pdf("Battle Plan", pdf_path)

        results = doc.search("crypto fund launch")
        assert len(results) >= 1
        assert any("crypto fund" in r.text for r in results)

    def test_search_no_results(self, tmp_path: Path):
        pdf_path = tmp_path / "bp.pdf"
        pdf_path.write_bytes(b"%PDF fake")
        pages = ["Completely unrelated content here."]
        with patch("digo.pdf_processor.pdfplumber.open", return_value=self._mock_pdf(pages)):
            doc = IndexedDocument.from_pdf("Battle Plan", pdf_path)
        results = doc.search("zzzznotfound")
        assert results == []

    def test_search_three_letter_keywords(self, tmp_path: Path):
        """Three-letter terms like CFV, DAO, API should be included in search."""
        pdf_path = tmp_path / "bp.pdf"
        pdf_path.write_bytes(b"%PDF fake")
        pages = [
            "The CFV metrics dashboard is live.",
            "Unrelated content about gardening tips.",
        ]
        with patch("digo.pdf_processor.pdfplumber.open", return_value=self._mock_pdf(pages)):
            doc = IndexedDocument.from_pdf("Battle Plan", pdf_path)
        results = doc.search("CFV metrics")
        assert len(results) >= 1
        assert "CFV" in results[0].text

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            IndexedDocument.from_pdf("Missing", Path("/no/such/file.pdf"))

    def test_full_text_includes_page_markers(self, tmp_path: Path):
        pdf_path = tmp_path / "x.pdf"
        pdf_path.write_bytes(b"%PDF fake")
        pages = ["First page content.", "Second page content."]
        with patch("digo.pdf_processor.pdfplumber.open", return_value=self._mock_pdf(pages)):
            doc = IndexedDocument.from_pdf("Doc", pdf_path)
        full = doc.full_text()
        assert "[Page 1]" in full
        assert "[Page 2]" in full

    def test_get_page_found(self, tmp_path: Path):
        pdf_path = tmp_path / "x.pdf"
        pdf_path.write_bytes(b"%PDF fake")
        with patch(
            "digo.pdf_processor.pdfplumber.open",
            return_value=self._mock_pdf(["Alpha.", "Beta."]),
        ):
            doc = IndexedDocument.from_pdf("Doc", pdf_path)
        chunk = doc.get_page(2)
        assert chunk is not None
        assert chunk.text == "Beta."

    def test_get_page_not_found(self, tmp_path: Path):
        pdf_path = tmp_path / "x.pdf"
        pdf_path.write_bytes(b"%PDF fake")
        with patch(
            "digo.pdf_processor.pdfplumber.open",
            return_value=self._mock_pdf(["Alpha."]),
        ):
            doc = IndexedDocument.from_pdf("Doc", pdf_path)
        assert doc.get_page(99) is None


# ---------------------------------------------------------------------------
# ResourceLibrary
# ---------------------------------------------------------------------------


class TestResourceLibrary:
    def _load_doc(self, lib: ResourceLibrary, name: str, pages: list[str], tmp_path: Path):
        pdf_path = tmp_path / f"{name}.pdf"
        pdf_path.write_bytes(b"%PDF fake")
        mock_pages = []
        for text in pages:
            mp = MagicMock()
            mp.extract_text.return_value = text
            mock_pages.append(mp)
        mock_pdf = MagicMock()
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        mock_pdf.pages = mock_pages
        with patch("digo.pdf_processor.pdfplumber.open", return_value=mock_pdf):
            lib.load(name, pdf_path)

    def test_loaded_names(self, tmp_path: Path):
        lib = ResourceLibrary()
        self._load_doc(lib, "Battle Plan", ["Content A"], tmp_path)
        assert "Battle Plan" in lib.loaded_names()

    def test_get_returns_document(self, tmp_path: Path):
        lib = ResourceLibrary()
        self._load_doc(lib, "Beyond Bitcoin", ["Bitcoin content"], tmp_path)
        doc = lib.get("Beyond Bitcoin")
        assert doc is not None
        assert doc.name == "Beyond Bitcoin"

    def test_get_returns_none_for_missing(self):
        lib = ResourceLibrary()
        assert lib.get("Nonexistent") is None

    def test_is_ready_false_when_empty(self):
        lib = ResourceLibrary()
        assert lib.is_ready() is False

    def test_is_ready_true_after_load(self, tmp_path: Path):
        lib = ResourceLibrary()
        self._load_doc(lib, "Doc", ["text"], tmp_path)
        assert lib.is_ready() is True

    def test_search_all(self, tmp_path: Path):
        lib = ResourceLibrary()
        self._load_doc(lib, "Battle Plan", ["crypto fund launch milestone"], tmp_path)
        self._load_doc(lib, "Beyond Bitcoin", ["bitcoin and crypto overview"], tmp_path)
        results = lib.search_all("crypto fund")
        assert "Battle Plan" in results
        assert "Beyond Bitcoin" in results

    def test_status_shows_loaded_docs(self, tmp_path: Path):
        lib = ResourceLibrary()
        self._load_doc(lib, "Battle Plan", ["text"], tmp_path)
        status = lib.status()
        assert "Battle Plan" in status
