"""Reciprocal Rank Fusion.

RRF constant default = 60 (engineering default, not claimed optimal).
Note: this project uses RRF, therefore the UI intentionally exposes NO alpha
weight parameter.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RrfCandidate:
    chunk_id: int
    rrf_score: float = 0.0
    dense_rank: int | None = None
    bm25_rank: int | None = None
    dense_similarity: float | None = None
    bm25_score: float | None = None
    rrf_rank: int = 0


def rrf_fuse(
    dense_hits: list,
    bm25_hits: list,
    rrf_constant: int = 60,
    candidate_k: int = 12,
) -> list[RrfCandidate]:
    """Fuse two ranked lists with Reciprocal Rank Fusion."""
    candidates: dict[int, RrfCandidate] = {}

    for rank, hit in enumerate(dense_hits, start=1):
        c = candidates.setdefault(hit.chunk_id, RrfCandidate(chunk_id=hit.chunk_id))
        c.dense_rank = rank
        c.dense_similarity = getattr(hit, "similarity", None)
        c.rrf_score += 1.0 / (rrf_constant + rank)

    for rank, hit in enumerate(bm25_hits, start=1):
        c = candidates.setdefault(hit.chunk_id, RrfCandidate(chunk_id=hit.chunk_id))
        c.bm25_rank = rank
        c.bm25_score = getattr(hit, "score", None)
        c.rrf_score += 1.0 / (rrf_constant + rank)

    ranked = sorted(candidates.values(), key=lambda c: c.rrf_score, reverse=True)[:candidate_k]
    for i, c in enumerate(ranked, start=1):
        c.rrf_rank = i
    return ranked
