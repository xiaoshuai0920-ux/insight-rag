"""Reranker provider abstraction.

Default: local CrossEncoder (BGE reranker family) via sentence-transformers.
If the local model is unavailable (not installed / download blocked), the
reranker reports unavailable and hybrid retrieval continues WITHOUT reranking
— graceful degradation per spec.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class RerankerProvider(ABC):
    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def rerank(self, query: str, documents: list[str], top_k: int) -> list[tuple[int, float]]:
        """Return list of (original_index, score) sorted by score desc."""
        ...


class RerankerUnavailable(Exception):
    pass


class NoopReranker(RerankerProvider):
    """Used when reranking is disabled: reports unavailable."""

    name = "disabled"

    def is_available(self) -> bool:
        return False

    def rerank(self, query: str, documents: list[str], top_k: int):
        raise RerankerUnavailable("Reranker 未启用")


def get_reranker_provider(enable: bool | None = None) -> RerankerProvider:
    from app.core.config import settings
    from app.services.settings_service import is_reranker_enabled

    if enable is False or (enable is None and not is_reranker_enabled()):
        return NoopReranker()
    if settings.RERANKER_PROVIDER == "local":
        from app.providers.reranker.local_cross_encoder import LocalCrossEncoderReranker

        return LocalCrossEncoderReranker(settings.RERANKER_MODEL)
    return NoopReranker()
