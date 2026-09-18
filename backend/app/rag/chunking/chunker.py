"""Structure-aware parent/child chunking.

Principle: retrieve small, generate large.

- Child chunks  ≈ 300-500 tokens (default 400), overlap ≈ 50 tokens.
- Parent chunks ≈ 800-1500 tokens (default 1000).
- When headings exist, split along sections first; otherwise recursive
  token-window fallback.
- Only CHILD chunks are embedded / retrievable; parents are recovered later
  via parent_id.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.rag.chunking.tokens import estimate_tokens
from app.rag.parsing.base import NormalizedDocument, Section

DEFAULT_CHILD_TOKENS = 400
DEFAULT_PARENT_TOKENS = 1000
DEFAULT_CHILD_OVERLAP = 50


@dataclass
class RawParent:
    heading: str
    heading_path: list[str]
    page_number: int | None
    content: str
    children: list["RawChild"] = field(default_factory=list)


@dataclass
class RawChild:
    heading: str
    heading_path: list[str]
    page_number: int | None
    content: str
    chunk_index: int = 0


def _split_by_tokens(text: str, max_tokens: int, overlap: int) -> list[str]:
    """Split long text into token-window pieces with character overlap.

    We split on paragraph/sentence boundaries when possible to avoid cutting
    sentences mid-way.
    """
    if estimate_tokens(text) <= max_tokens:
        return [text] if text.strip() else []

    # Candidate cut points: paragraph > sentence > hard cut
    pieces: list[str] = []
    buf: list[str] = []
    buf_tokens = 0
    for para in text.split("\n"):
        para = para.strip()
        para_tokens = estimate_tokens(para)
        if buf_tokens + para_tokens > max_tokens and buf:
            pieces.append("\n".join(buf))
            # keep tail overlap (approximate by chars: overlap_tokens * 2.2 chars)
            tail = pieces[-1][-int(overlap * 2.2):] if overlap > 0 else ""
            buf = [tail] if tail.strip() else []
            buf_tokens = estimate_tokens(tail)
        if para_tokens > max_tokens:
            # hard split long paragraph by sentences then chars
            for piece in _hard_split(para, max_tokens, overlap):
                pieces.append(piece)
            buf, buf_tokens = [], 0
            continue
        buf.append(para)
        buf_tokens += para_tokens
    if buf and "\n".join(buf).strip():
        pieces.append("\n".join(buf))
    return [p for p in pieces if p.strip()]


def _hard_split(text: str, max_tokens: int, overlap: int) -> list[str]:
    import re

    sentences = re.split(r"(?<=[。！？!?；;])\s*", text)
    pieces: list[str] = []
    buf: list[str] = []
    buf_tokens = 0
    for sent in sentences:
        sent_tokens = estimate_tokens(sent)
        if sent_tokens > max_tokens:
            if buf:
                pieces.append("".join(buf))
                buf, buf_tokens = [], 0
            # char-level split
            step = max(50, int(max_tokens * 2.0))
            win_overlap = int(overlap * 2.0)
            start = 0
            while start < len(sent):
                chunk = sent[start : start + step]
                if chunk.strip():
                    pieces.append(chunk)
                if start + step >= len(sent):
                    break
                start += step - win_overlap
            continue
        if buf_tokens + sent_tokens > max_tokens and buf:
            pieces.append("".join(buf))
            tail = pieces[-1][-int(overlap * 2.2):] if overlap > 0 else ""
            buf = [tail] if tail.strip() else []
            buf_tokens = estimate_tokens(tail)
        buf.append(sent)
        buf_tokens += sent_tokens
    if buf and "".join(buf).strip():
        pieces.append("".join(buf))
    return [p for p in pieces if p.strip()]


def build_parent_child_chunks(
    normalized: NormalizedDocument,
    child_tokens: int = DEFAULT_CHILD_TOKENS,
    parent_tokens: int = DEFAULT_PARENT_TOKENS,
    child_overlap: int = DEFAULT_CHILD_OVERLAP,
) -> list[RawParent]:
    """Return parent chunks, each with its child chunks attached."""
    parents: list[RawParent] = []
    current_parent: RawParent | None = None

    def close_parent() -> None:
        nonlocal current_parent
        current_parent = None

    for section in normalized.sections:
        sec_tokens = estimate_tokens(section.content)
        if sec_tokens == 0:
            continue

        # Start a new parent when: no parent, section is big enough to be its
        # own parent, or heading level <= 2 begins a new logical block.
        start_new = (
            current_parent is None
            or sec_tokens >= parent_tokens * 0.6
            or (section.level <= 2 and section.heading)
        )

        if start_new:
            close_parent()
            current_parent = RawParent(
                heading=section.heading,
                heading_path=list(section.heading_path) or ([section.heading] if section.heading else []),
                page_number=section.page_number,
                content=section.content,
            )
            parents.append(current_parent)
        else:
            assert current_parent is not None
            current_parent.content += "\n\n" + section.content

        # children from this section
        assert current_parent is not None
        for piece in _split_by_tokens(section.content, child_tokens, child_overlap):
            current_parent.children.append(
                RawChild(
                    heading=section.heading,
                    heading_path=list(section.heading_path) or ([section.heading] if section.heading else []),
                    page_number=section.page_number,
                    content=piece,
                )
            )

        # if parent grew beyond the limit, close it after this section
        if estimate_tokens(current_parent.content) >= parent_tokens:
            close_parent()

    # A parent with no children (e.g. content shorter than a child window but
    # non-empty) still needs one child so it can be retrieved.
    for parent in parents:
        if not parent.children and parent.content.strip():
            parent.children.append(
                RawChild(
                    heading=parent.heading,
                    heading_path=list(parent.heading_path),
                    page_number=parent.page_number,
                    content=parent.content,
                )
            )
    return [p for p in parents if p.children]
