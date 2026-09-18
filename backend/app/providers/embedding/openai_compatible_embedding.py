"""OpenAI-compatible embedding provider."""
from __future__ import annotations

from app.core.config import settings
from app.providers.embedding.base import EmbeddingError, EmbeddingProvider


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    name = "openai_compatible"

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or settings.OPENAI_COMPATIBLE_BASE_URL).rstrip("/")
        self.api_key = settings.OPENAI_COMPATIBLE_API_KEY
        self.model = model or settings.OPENAI_COMPATIBLE_EMBEDDING_MODEL

    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not self.is_configured():
            raise EmbeddingError(
                "未配置 OpenAI Compatible Embedding（.env 中 OPENAI_COMPATIBLE_* 为空）"
            )
        try:
            from openai import OpenAI

            client = OpenAI(base_url=f"{self.base_url}/v1", api_key=self.api_key, timeout=120)
            out: list[list[float]] = []
            batch = 64
            for i in range(0, len(texts), batch):
                part = texts[i : i + batch]
                resp = client.embeddings.create(model=self.model, input=part)
                out.extend([list(map(float, d.embedding)) for d in resp.data])
            return out
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(f"OpenAI Compatible embedding 调用失败: {exc}") from exc

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
