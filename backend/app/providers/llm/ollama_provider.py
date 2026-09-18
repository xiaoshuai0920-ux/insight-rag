"""Ollama LLM provider (local, OpenAI-free)."""
from __future__ import annotations

import json
from typing import Generator

import httpx

from app.core.config import settings
from app.providers.llm.base import LLMError, LLMProvider


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_LLM_MODEL

    def is_configured(self) -> bool:
        return bool(self.base_url)

    def list_models(self) -> list[str]:
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception:
            return []

    def test_connection(self) -> dict:
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            models = [m.get("name", "") for m in resp.json().get("models", [])]
            return {
                "ok": True,
                "provider": self.name,
                "models": models,
                "model_available": self.model in models,
                "message": f"已连接 Ollama（{len(models)} 个模型）",
            }
        except Exception as exc:
            return {
                "ok": False,
                "provider": self.name,
                "message": f"无法连接 Ollama 服务: {exc}",
            }

    def stream_chat(
        self, messages: list[dict], temperature: float = 0.3
    ) -> Generator[str, None, None]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature},
        }
        try:
            with httpx.stream(
                "POST", f"{self.base_url}/api/chat", json=payload, timeout=300
            ) as resp:
                if resp.status_code != 200:
                    raise LLMError(f"Ollama 返回错误: HTTP {resp.status_code}")
                for line in resp.iter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if data.get("error"):
                        raise LLMError(f"Ollama 错误: {data['error']}")
                    piece = (data.get("message") or {}).get("content", "")
                    if piece:
                        yield piece
                    if data.get("done"):
                        break
        except httpx.HTTPError as exc:
            raise LLMError(f"无法连接 Ollama（{self.base_url}）: {exc}") from exc
