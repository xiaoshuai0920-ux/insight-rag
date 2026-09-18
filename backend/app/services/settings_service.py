"""Runtime settings service (non-secret configuration in app_settings table).

API keys are NEVER stored here — they only come from .env.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AppSetting, EmbeddingProfile

DEFAULTS: dict[str, Any] = {
    "llm_provider": "ollama",
    "llm_model": settings.OLLAMA_LLM_MODEL,
    "llm_endpoint": settings.OLLAMA_BASE_URL,
    "embedding_provider": settings.EMBEDDING_PROVIDER,
    "embedding_model": settings.OLLAMA_EMBEDDING_MODEL,
    "reranker_enabled": False,  # enabled only when local model is available
    "reranker_model": settings.RERANKER_MODEL,
    "active_embedding_profile_id": None,
}


def get_setting(db: Session, key: str, default: Any = None) -> Any:
    row = db.get(AppSetting, key)
    if row is None:
        return DEFAULTS.get(key, default)
    return row.value.get("v", DEFAULTS.get(key, default))


def set_setting(db: Session, key: str, value: Any) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value={"v": value})
        db.add(row)
    else:
        row.value = {"v": value}


def get_effective_llm_provider() -> str:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        return str(get_setting(db, "llm_provider", "ollama"))
    finally:
        db.close()


def get_effective_embedding_provider() -> str:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        return str(get_setting(db, "embedding_provider", settings.EMBEDDING_PROVIDER))
    finally:
        db.close()


def is_reranker_enabled() -> bool:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        return bool(get_setting(db, "reranker_enabled", False))
    finally:
        db.close()


def get_active_embedding_profile(db: Session) -> EmbeddingProfile | None:
    profile_id = get_setting(db, "active_embedding_profile_id", None)
    if profile_id:
        profile = db.get(EmbeddingProfile, profile_id)
        if profile is not None and profile.status == "ACTIVE":
            return profile
    # fall back to the single ACTIVE profile
    return (
        db.query(EmbeddingProfile)
        .filter(EmbeddingProfile.status == "ACTIVE")
        .order_by(EmbeddingProfile.activated_at.desc())
        .first()
    )


def export_settings(db: Session) -> dict[str, Any]:
    """Snapshot of effective settings for the Settings page (no secrets)."""
    out: dict[str, Any] = {}
    for key in DEFAULTS:
        out[key] = get_setting(db, key, DEFAULTS[key])
    # Provider availability flags (env-driven)
    out["openai_compatible_configured"] = bool(
        settings.OPENAI_COMPATIBLE_BASE_URL and settings.OPENAI_COMPATIBLE_API_KEY
    )
    out["deepseek_configured"] = bool(
        settings.DEEPSEEK_BASE_URL and settings.DEEPSEEK_API_KEY
    )
    out["ollama_base_url"] = settings.OLLAMA_BASE_URL
    return out


def apply_settings(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "llm_provider",
        "llm_model",
        "llm_endpoint",
        "embedding_provider",
        "embedding_model",
        "reranker_enabled",
        "reranker_model",
    }
    for key, value in payload.items():
        if key in allowed:
            set_setting(db, key, value)
    db.commit()
    return export_settings(db)


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
