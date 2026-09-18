"""Markdown parser: headings # / ## / ### become the section structure."""
from __future__ import annotations

import re
from pathlib import Path

from app.rag.parsing.base import NormalizedDocument, Section, SourceFormat

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


class MarkdownParser:
    supported_format = SourceFormat.MARKDOWN

    def parse(self, file_path: str | Path) -> NormalizedDocument:
        path = Path(file_path)
        raw = path.read_text(encoding="utf-8", errors="replace")
        raw = self._strip_front_matter(raw)

        sections: list[Section] = []
        heading_paths: list[str] = []
        current: Section | None = None

        for line in raw.split("\n"):
            m = _HEADING_RE.match(line.strip())
            if m:
                level = len(m.group(1))
                text = m.group(2).strip()
                heading_paths = heading_paths[: level - 1]
                heading_paths.append(text)
                current = Section(
                    heading=text, heading_path=list(heading_paths), content="", level=level
                )
                sections.append(current)
            else:
                if current is None:
                    current = Section(heading="", content="", level=1)
                    sections.append(current)
                current.content += line + "\n"

        for sec in sections:
            sec.content = sec.content.strip()

        normalized = NormalizedDocument(
            title=path.stem,
            format=SourceFormat.MARKDOWN,
            sections=[s for s in sections if s.content or s.heading],
        )
        normalized.compute_stats()
        return normalized

    def _strip_front_matter(self, raw: str) -> str:
        if raw.startswith("---"):
            end = raw.find("\n---", 3)
            if end != -1:
                return raw[end + 4:].lstrip("\n")
        return raw
