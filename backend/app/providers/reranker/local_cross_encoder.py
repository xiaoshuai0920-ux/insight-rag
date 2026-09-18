"""Local CrossEncoder reranker using sentence-transformers.

Model weights are loaded lazily on first use. If sentence-transformers or the
model file is unavailable, `is_available()` returns False and callers skip
reranking gracefully (hybrid still runs).
"""
from __future__ import annotations

import logging
import threading

from app.providers.reranker.base import RerankerProvider

logger = logging.getLogger(__name__)


class LocalCrossEncoderReranker(RerankerProvider):
    name = "local_cross_encoder"

    _model = None
    _load_failed = False
    _lock = threading.Lock()

    def __init__(self, model_name: str = "BAAI/bge-reranker-base") -> None:
        self.model_name = model_name

    def _load(self):
        if LocalCrossEncoderReranker._model is not None:
            return LocalCrossEncoderReranker._model
        if LocalCrossEncoderReranker._load_failed:
            return None
        with LocalCrossEncoderReranker._lock:
            if LocalCrossEncoderReranker._model is not None:
                return LocalCrossEncoderReranker._model
            if LocalCrossEncoderReranker._load_failed:
                return None
            try:
                import os

                # Prefer the local HF cache when complete; only go online as fallback.
                try:
                    os.environ["HF_HUB_OFFLINE"] = "1"
                    os.environ["TRANSFORMERS_OFFLINE"] = "1"
                    from sentence_transformers import CrossEncoder

                    model = CrossEncoder(
                        self.model_name,
                        max_length=512,
                        trust_remote_code=False,
                    )
                except Exception:
                    # Cache miss: allow online download (respect HF_ENDPOINT, e.g. hf-mirror).
                    os.environ.pop("HF_HUB_OFFLINE", None)
                    os.environ.pop("TRANSFORMERS_OFFLINE", None)
                    from sentence_transformers import CrossEncoder

                    model = CrossEncoder(
                        self.model_name,
                        max_length=512,
                        local_files_only=False,
                        trust_remote_code=False,
                    )
                LocalCrossEncoderReranker._model = model
                logger.info("Reranker model loaded: %s", self.model_name)
                return model
            except Exception as exc:  # pragma: no cover - depends on env
                logger.warning("Reranker model unavailable (%s): %s", self.model_name, exc)
                LocalCrossEncoderReranker._load_failed = True
                return None

    def is_available(self) -> bool:
        return self._load() is not None

    def rerank(self, query: str, documents: list[str], top_k: int) -> list[tuple[int, float]]:
        model = self._load()
        if model is None:
            from app.providers.reranker.base import RerankerUnavailable

            raise RerankerUnavailable(f"本地 Reranker 模型不可用: {self.model_name}")
        pairs = [[query, doc] for doc in documents]
        scores = model.predict(pairs)
        ranked = sorted(
            enumerate((float(s) for s in scores)), key=lambda t: t[1], reverse=True
        )
        return [(idx, score) for idx, score in ranked[:top_k]]
