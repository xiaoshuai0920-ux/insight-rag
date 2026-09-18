"""Plain text parser: no structure — degrade to paragraph based sections."""
from __future__ import annotations

from pathlib import Path

from app.rag.parsing.base import NormalizedDocument, Section, SourceFormat


class TextParser:
    supported_format = SourceFormat.TXT

    def parse(self, file_path: str | Path) -> NormalizedDocument:
        path = Path(file_path)
        raw = path.read_text(encoding="utf-8", errors="replace")

        sections: list[Section] = []
        paragraph_buf: list[str] = []
        heading_paths: list[str] = []
        index = 0

        def flush() -> None:
            nonlocal paragraph_buf, index
            text = "\n".join(paragraph_buf).strip()
            if text:
                index += 1
                sections.append(
                    Section(
                        heading=f"段落 {index}",
                        heading_path=list(heading_paths) or [f"段落 {index}"],
                        content=text,
                        level=2,
                    )
                )
            paragraph_buf = []

        for block in raw.split("\n\n"):
            block = block.strip()
            if not block:
                continue
            paragraph_buf.append(block)
            # flush roughly every ~1200 chars to create usable section boundaries
            if sum(len(p) for p in paragraph_buf) > 1200:
                flush()
        flush()

        normalized = NormalizedDocument(
            title=path.stem, format=SourceFormat.TXT, sections=sections
        )
        normalized.compute_stats()
        return normalized
