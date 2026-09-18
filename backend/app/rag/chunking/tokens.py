"""Token estimation utilities for Chinese + English mixed text.

Uses a lightweight heuristic: CJK chars ≈ 1 token each (for typical Chinese
models 1 char ≈ 0.6-1 token), ASCII words ≈ 1.3 tokens per word. This is a
conservative engineering estimate — NOT a claim of tokenizer-exact counts.
"""
from __future__ import annotations

import re

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
_ASCII_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    cjk = len(_CJK_RE.findall(text))
    ascii_words = len(_ASCII_WORD_RE.findall(text))
    other = len(text) - sum(len(m.group(0)) for m in _ASCII_WORD_RE.finditer(text)) - cjk
    return max(1, cjk + int(ascii_words * 1.3) + int(other * 0.4))
