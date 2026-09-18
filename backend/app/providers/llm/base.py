"""LLM provider abstraction."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generator

from app.core.config import settings


class LLMError(Exception):
    """Raised when the LLM provider is not configured or fails."""


class LLMNotConfigured(LLMError):
    pass


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def list_models(self) -> list[str]: ...

    @abstractmethod
    def test_connection(self) -> dict: ...

    @abstractmethod
    def stream_chat(
        self, messages: list[dict], temperature: float = 0.3
    ) -> Generator[str, None, None]:
        """Yield answer text chunks. Raise LLMError on failure."""


def get_llm_provider(provider_name: str | None = None) -> LLMProvider:
    from app.services.settings_service import get_effective_llm_provider

    name = provider_name or get_effective_llm_provider()
    if name == "ollama":
        from app.providers.llm.ollama_provider import OllamaProvider

        return OllamaProvider()
    if name == "openai_compatible":
        from app.providers.llm.openai_compatible_provider import OpenAICompatibleProvider

        return OpenAICompatibleProvider()
    raise LLMError(f"未知的 LLM Provider: {name}")


def ollama_available(base_url: str | None = None) -> bool:
    import httpx

    url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
    try:
        resp = httpx.get(f"{url}/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False
