"""
PDF processor for Digo the Scribe.

Loads, indexes, and allows semantic retrieval of content from:
  • The Digital Gold Co Battle Plan
  • Beyond Bitcoin by John Gotts
  • The Digital Gold White Paper

IMPORTANT: Digo never fabricates content from these documents.  If a passage
cannot be located with high confidence the query is flagged for human review.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """A page-level chunk of text extracted from a PDF."""

    source: str  # logical name of the document, e.g. "Battle Plan"
    file_path: str
    page_number: int  # 1-indexed
    text: str

    @property
    def reference(self) -> str:
        return f"{self.source}, page {self.page_number}"


@dataclass
class IndexedDocument:
    """An in-memory index of all chunks from a single PDF."""

    name: str
    file_path: Path
    chunks: list[DocumentChunk] = field(default_factory=list)
    _text_hash: str = field(default="", init=False, repr=False)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @classmethod
    def from_pdf(cls, name: str, path: Path) -> IndexedDocument:
        """Load a PDF and extract text page by page."""
        if not path.exists():
            raise FileNotFoundError(
                f"PDF for '{name}' not found at {path}. Please provide the file and restart Digo."
            )

        doc = cls(name=name, file_path=path)
        raw_bytes = path.read_bytes()
        doc._text_hash = hashlib.sha256(raw_bytes).hexdigest()

        logger.info("Loading '%s' from %s …", name, path)
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                text = text.strip()
                if text:
                    doc.chunks.append(
                        DocumentChunk(
                            source=name,
                            file_path=str(path),
                            page_number=i,
                            text=text,
                        )
                    )

        logger.info(
            "Loaded %d pages from '%s' (sha256: %s…)",
            len(doc.chunks),
            name,
            doc._text_hash[:12],
        )
        return doc

    # ------------------------------------------------------------------
    # Retrieval helpers
    # ------------------------------------------------------------------

    def full_text(self) -> str:
        """Return the complete document text (all pages joined)."""
        return "\n\n".join(f"[Page {c.page_number}]\n{c.text}" for c in self.chunks)

    def search(self, query: str, max_results: int = 5) -> list[DocumentChunk]:
        """
        Simple keyword-based search.  Returns the chunks most likely to
        contain relevant content for *query*.

        This is intentionally transparent and deterministic so that every
        retrieved passage can be traced back to an exact page number.
        """
        query_lower = query.lower()
        keywords = [w for w in query_lower.split() if len(w) >= 3]

        scored: list[tuple[int, DocumentChunk]] = []
        for chunk in self.chunks:
            text_lower = chunk.text.lower()
            score = sum(text_lower.count(kw) for kw in keywords)
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored[:max_results]]

    def get_page(self, page_number: int) -> DocumentChunk | None:
        for chunk in self.chunks:
            if chunk.page_number == page_number:
                return chunk
        return None

    def summary_dict(self) -> dict:
        return {
            "name": self.name,
            "file_path": str(self.file_path),
            "total_pages_with_text": len(self.chunks),
            "sha256": self._text_hash,
        }


class ResourceLibrary:
    """
    Manages all PDF resources available to Digo.

    Documents are added at runtime.  Attempting to use a document that has not
    been loaded returns a clear, honest message rather than a hallucinated answer.
    """

    def __init__(self) -> None:
        self._documents: dict[str, IndexedDocument] = {}

    def load(self, name: str, path: Path) -> IndexedDocument:
        doc = IndexedDocument.from_pdf(name, path)
        self._documents[name] = doc
        return doc

    def get(self, name: str) -> IndexedDocument | None:
        return self._documents.get(name)

    def loaded_names(self) -> list[str]:
        return list(self._documents.keys())

    def search_all(self, query: str, max_per_doc: int = 3) -> dict[str, list[DocumentChunk]]:
        """Search across all loaded documents."""
        return {
            name: doc.search(query, max_results=max_per_doc)
            for name, doc in self._documents.items()
        }

    def is_ready(self) -> bool:
        return bool(self._documents)

    def status(self) -> str:
        if not self._documents:
            return "No documents loaded."
        lines = ["Loaded documents:"]
        for doc in self._documents.values():
            s = doc.summary_dict()
            lines.append(f"  • {s['name']} — {s['total_pages_with_text']} pages ({s['file_path']})")
        return "\n".join(lines)
