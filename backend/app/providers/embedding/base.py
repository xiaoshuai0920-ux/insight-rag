"""Embedding provider abstraction."""
from __future__ import annotations

from abc import ABC


class EmbeddingError(Exception):
    pass


class EmbeddingNotReady(EmbeddingError):
    pass


class EmbeddingProvider(ABC):
    name: str = "base"

    def is_configured(self) -> bool:
        return True

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError

    def get_dimension(self) -> int | None:
        return None

    def test_connection(self) -> dict:
        try:
            vec = self.embed_query("测试")
            return {
                "ok": True,
                "provider": self.name,
                "dimension": len(vec),
                "message": "Embedding 连接正常",
            }
        except Exception as exc:
            return {"ok": False, "provider": self.name, "message": str(exc)}


def get_embedding_provider(provider_name: str | None = None, model: str | None = None):
    from app.core.config import settings
    from app.services.settings_service import get_effective_embedding_provider

    name = provider_name or get_effective_embedding_provider()
    if name == "ollama":
        from app.providers.embedding.ollama_embedding import OllamaEmbeddingProvider

        return OllamaEmbeddingProvider(model=model or settings.OLLAMA_EMBEDDING_MODEL)
    if name == "openai_compatible":
        from app.providers.embedding.openai_compatible_embedding import (
            OpenAICompatibleEmbeddingProvider,
        )

        return OpenAICompatibleEmbeddingProvider(model=model)
    raise EmbeddingError(f"未知的 Embedding Provider: {name}")
