"""Ollama embedding provider (/api/embed or /api/embeddings)."""
from __future__ import annotations

import httpx

from app.core.config import settings
from app.providers.embedding.base import EmbeddingError, EmbeddingProvider


class OllamaEmbeddingProvider(EmbeddingProvider):
    name = "ollama"

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_EMBEDDING_MODEL

    def is_configured(self) -> bool:
        return bool(self.base_url and self.model)

    def model_installed(self) -> bool:
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            models = [m.get("name", "") for m in resp.json().get("models", [])]
            return self.model in models or self.model.split(":")[0] in models
        except Exception:
            return False

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            resp = httpx.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings")
            if embeddings is None and "embedding" in data:  # legacy single-input
                embeddings = [data["embedding"]]
            if not embeddings:
                raise EmbeddingError("Ollama embedding 返回为空")
            return [list(map(float, e)) for e in embeddings]
        except httpx.HTTPError as exc:
            raise EmbeddingError(f"Ollama embedding 调用失败: {exc}") from exc

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def get_dimension(self) -> int | None:
        try:
            return len(self.embed_query("dim"))
        except Exception:
            return None
