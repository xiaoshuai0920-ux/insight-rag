"""Unified document parsing interface.

All parsers convert source files into a NormalizedDocument made of Sections,
so downstream chunking never needs to care about the source format.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class SourceFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    MARKDOWN = "markdown"
    TXT = "txt"


class ScanPdfError(ValueError):
    """Raised when a PDF contains no extractable text (likely a scanned file)."""


@dataclass
class Section:
    """A logical block of the document: a heading plus its body text."""

    heading: str = ""
    heading_path: list[str] = field(default_factory=list)
    page_number: int | None = None
    content: str = ""
    level: int = 1


@dataclass
class NormalizedDocument:
    title: str
    format: SourceFormat
    sections: list[Section] = field(default_factory=list)
    page_count: int = 0
    char_count: int = 0

    def compute_stats(self) -> None:
        self.page_count = max(
            (s.page_number or 0) for s in self.sections
        ) if self.sections else 0
        self.char_count = sum(len(s.content) for s in self.sections)


class DocumentParser:
    """Base interface. Subclasses parse one source format."""

    supported_format: SourceFormat

    def parse(self, file_path: str | Path) -> NormalizedDocument:
        raise NotImplementedError


def get_parser(file_type: str) -> DocumentParser:
    from app.rag.parsing.docx_parser import DocxParser
    from app.rag.parsing.markdown_parser import MarkdownParser
    from app.rag.parsing.pdf_parser import PdfParser
    from app.rag.parsing.text_parser import TextParser

    suffix = (file_type or "").lower().lstrip(".")
    mapping = {
        "pdf": PdfParser,
        "docx": DocxParser,
        "doc": DocxParser,
        "md": MarkdownParser,
        "markdown": MarkdownParser,
        "txt": TextParser,
    }
    cls = mapping.get(suffix)
    if cls is None:
        raise ValueError(f"不支持的文件格式: {file_type}（支持 PDF / DOCX / Markdown / TXT）")
    return cls()
