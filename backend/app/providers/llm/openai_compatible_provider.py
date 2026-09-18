"""OpenAI-compatible LLM provider (works with any OpenAI-style endpoint).

API key comes ONLY from .env. When missing, provider reports 'not configured'
instead of raising at import/app-startup time.
"""
from __future__ import annotations

from typing import Generator

from app.core.config import settings
from app.providers.llm.base import LLMError, LLMNotConfigured, LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    name = "openai_compatible"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.OPENAI_COMPATIBLE_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.OPENAI_COMPATIBLE_API_KEY
        self.model = model or settings.OPENAI_COMPATIBLE_LLM_MODEL

    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    def list_models(self) -> list[str]:
        if not self.is_configured():
            return []
        try:
            from openai import OpenAI

            client = OpenAI(base_url=f"{self.base_url}/v1", api_key=self.api_key, timeout=10)
            return [m.id for m in client.models.list().data]
        except Exception:
            return []

    def test_connection(self) -> dict:
        if not self.base_url or not self.api_key:
            return {
                "ok": False,
                "provider": self.name,
                "not_configured": True,
                "message": "未配置 API Key（请在 .env 中设置 OPENAI_COMPATIBLE_BASE_URL / OPENAI_COMPATIBLE_API_KEY / OPENAI_COMPATIBLE_LLM_MODEL）",
            }
        try:
            from openai import OpenAI

            client = OpenAI(base_url=f"{self.base_url}/v1", api_key=self.api_key, timeout=15)
            models = [m.id for m in client.models.list().data]
            return {
                "ok": True,
                "provider": self.name,
                "models": models,
                "model_available": self.model in models,
                "message": "连接成功（OpenAI Compatible）",
            }
        except Exception as exc:
            return {"ok": False, "provider": self.name, "message": f"连接失败: {exc}"}

    def stream_chat(
        self, messages: list[dict], temperature: float = 0.3
    ) -> Generator[str, None, None]:
        if not self.is_configured():
            raise LLMNotConfigured(
                "OpenAI Compatible Provider 未配置 API Key，请在 .env 中填写后重启"
            )
        try:
            from openai import OpenAI

            client = OpenAI(base_url=f"{self.base_url}/v1", api_key=self.api_key, timeout=300)
            stream = client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                stream=True,
            )
            for event in stream:
                if event.choices and event.choices[0].delta and event.choices[0].delta.content:
                    yield event.choices[0].delta.content
        except Exception as exc:
            raise LLMError(f"OpenAI Compatible 调用失败: {exc}") from exc
