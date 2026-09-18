"""Ollama + stats + misc API."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.config import settings as env_settings
from app.db.session import get_db
from app.models import User
from app.providers.llm.base import ollama_available
from app.providers.llm.ollama_provider import OllamaProvider
from app.services.stats_service import (
    recent_conversations,
    recent_knowledge_bases,
    user_dashboard_stats,
)

router = APIRouter(prefix="/api", tags=["misc"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "app": "InsightRAG",
        "ollama_available": ollama_available(),
    }


@router.get("/ollama/models")
def ollama_models(current_user: User = Depends(get_current_user)):
    provider = OllamaProvider()
    if not ollama_available():
        return {"available": False, "models": [], "base_url": env_settings.OLLAMA_BASE_URL}
    return {
        "available": True,
        "models": provider.list_models(),
        "base_url": env_settings.OLLAMA_BASE_URL,
    }


@router.get("/stats/dashboard")
def dashboard_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        "summary": user_dashboard_stats(db, current_user.id),
        "recent_knowledge_bases": recent_knowledge_bases(db, current_user.id),
        "recent_conversations": recent_conversations(db, current_user.id),
    }
