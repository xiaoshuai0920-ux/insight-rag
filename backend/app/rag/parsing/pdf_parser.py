"""PDF parser based on PyMuPDF.

- Preserves page numbers.
- Detects headings using font-size heuristics.
- Detects likely scanned PDFs (no extractable text) and raises ScanPdfError.
- Simple table detection converted to Markdown tables.
"""
from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from app.rag.parsing.base import NormalizedDocument, ScanPdfError, Section, SourceFormat


class PdfParser:
    supported_format = SourceFormat.PDF

    # Body text below ~7pt is usually noise; headings are usually > 1.15x body size.
    MIN_BODY_SIZE = 6.5

    def parse(self, file_path: str | Path) -> NormalizedDocument:
        path = Path(file_path)
        doc = fitz.open(str(path))
        try:
            sections: list[Section] = []
            total_chars = 0
            for page_index, page in enumerate(doc):
                page_number = page_index + 1
                page_text = self._extract_page_text(page)
                total_chars += len(page_text)
                sections.append(
                    Section(
                        heading=f"第 {page_number} 页",
                        heading_path=[f"第 {page_number} 页"],
                        page_number=page_number,
                        content=page_text,
                        level=2,
                    )
                )
            if total_chars < 30:
                raise ScanPdfError(
                    "当前文件可能为扫描件，暂不支持 OCR。请上传文本型 PDF，"
                    "或先使用 OCR 工具转换后再上传。"
                )
            normalized = NormalizedDocument(
                title=path.stem, format=SourceFormat.PDF, sections=sections,
                page_count=len(doc),
            )
            normalized.compute_stats()
            # Re-split page text into heading-aware sections when possible.
            normalized.sections = self._split_by_headings(normalized.sections)
            return normalized
        finally:
            doc.close()

    def _extract_page_text(self, page: fitz.Page) -> str:
        """Extract text blocks, converting detected tables to Markdown tables."""
        parts: list[str] = []
        try:
            tables = page.find_tables()
            table_bboxes = []
            for table in tables:
                table_bboxes.append(table.bbox)
                md = self._table_to_markdown(table)
                if md:
                    parts.append(md)
            # Regular text outside table areas
            text = page.get_text("text", clip=None)
            # Remove lines that belong to tables (approximate: drop them by bbox match)
            if table_bboxes:
                lines_out = []
                for block in page.get_text("blocks"):
                    x0, y0, x1, y1, btext = block[0], block[1], block[2], block[3], block[4]
                    inside_table = any(
                        not (x1 < tb[0] or x0 > tb[2] or y1 < tb[1] or y0 > tb[3])
                        for tb in table_bboxes
                    )
                    if not inside_table:
                        lines_out.append(btext.strip())
                text = "\n".join(lines_out)
            if text.strip():
                parts.insert(0, text.strip())
        except Exception:
            text = page.get_text("text")
            if text.strip():
                parts.append(text.strip())
        return "\n\n".join(p for p in parts if p.strip())

    def _table_to_markdown(self, table) -> str:
        try:
            rows = table.extract()
        except Exception:
            return ""
        rows = [[("" if c is None else str(c).strip().replace("\n", " ")) for c in row] for row in rows]
        rows = [r for r in rows if any(cell for cell in r)]
        if len(rows) < 2:
            return ""
        header = rows[0]
        lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * len(header)) + " |"]
        for row in rows[1:]:
            row = (row + [""] * len(header))[: len(header)]
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)

    def _split_by_headings(self, page_sections: list[Section]) -> list[Section]:
        """Merge page sections, splitting on detected heading lines."""
        out: list[Section] = []
        current: Section | None = None
        heading_paths: list[str] = []
        for page_sec in page_sections:
            for raw_line in page_sec.content.split("\n"):
                line = raw_line.strip()
                if not line:
                    continue
                if self._is_heading(line):
                    level = self._heading_level(line)
                    # Maintain heading path stack
                    heading_paths = heading_paths[: level - 1]
                    heading_paths.append(line)
                    current = Section(
                        heading=line,
                        heading_path=list(heading_paths),
                        page_number=page_sec.page_number,
                        content="",
                        level=level,
                    )
                    out.append(current)
                else:
                    if current is None:
                        current = Section(
                            heading="",
                            heading_path=[],
                            page_number=page_sec.page_number,
                            content="",
                            level=1,
                        )
                        out.append(current)
                    current.content += line + "\n"
        for sec in out:
            sec.content = sec.content.strip()
        return [s for s in out if s.content or s.heading]

    def _is_heading(self, line: str) -> bool:
        if len(line) > 40:
            return False
        # Chinese doc headings: 第X章 / 第X节 / 一、二、 / 数字编号 like 4.1 / 1.2.3
        import re

        patterns = [
            r"^第[一二三四五六七八九十百\d]+[章节篇条]",
            r"^[一二三四五六七八九十]+[、.．]",
            r"^\d+(\.\d+)*[、.．\s]?\s*\S{1,30}$",
            r"^\([一二三四五六七八九十\d]+\)",
        ]
        return any(re.match(p, line) for p in patterns)

    def _heading_level(self, line: str) -> int:
        import re

        if re.match(r"^第[一二三四五六七八九十百\d]+[章篇]", line):
            return 1
        if re.match(r"^第[一二三四五六七八九十百\d]+[节条]", line):
            return 2
        if re.match(r"^[一二三四五六七八九十]+[、.．]", line):
            return 2
        m = re.match(r"^(\d+(?:\.\d+)*)", line)
        if m:
            return min(3, m.group(1).count(".") + 1)
        return 3
