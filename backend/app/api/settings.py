"""Settings API: runtime config, tests, embedding impact/reindex."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.config import settings as env_settings
from app.db.session import get_db
from app.models import User
from app.providers.llm.base import get_llm_provider, ollama_available
from app.providers.reranker.base import get_reranker_provider
from app.services.reindex_service import (
    compute_embedding_impact,
    reindex_status,
    retry_rebuild,
    start_embedding_rebuild,
)
from app.services.settings_service import apply_settings, export_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdateRequest(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_endpoint: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    reranker_enabled: bool | None = None
    reranker_model: str | None = None


@router.get("")
def get_settings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = export_settings(db)
    data["deepseek"] = {
        "base_url": env_settings.DEEPSEEK_BASE_URL,
        "configured": bool(env_settings.DEEPSEEK_BASE_URL and env_settings.DEEPSEEK_API_KEY),
        "model": env_settings.DEEPSEEK_LLM_MODEL,
    }
    data["ollama"] = {
        "base_url": env_settings.OLLAMA_BASE_URL,
        "available": ollama_available(),
    }
    rr = get_reranker_provider(enable=True)
    data["reranker_available"] = rr.is_available()
    return data


@router.put("")
def update_settings(
    payload: SettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return apply_settings(db, payload.model_dump(exclude_none=True, exclude_unset=True))


@router.post("/test-llm")
def test_llm(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    provider = get_llm_provider()
    result = provider.test_connection()
    return result


@router.post("/test-reranker")
def test_reranker(current_user: User = Depends(get_current_user)):
    rr = get_reranker_provider(enable=True)
    if not rr.is_available():
        return {
            "ok": False,
            "provider": rr.name,
            "message": "本地 Reranker 模型未就绪（sentence-transformers 或模型文件不可用）。"
            "可关闭 Reranker，Hybrid 检索不受影响。",
        }
    try:
        ranked = rr.rerank("报销标准是多少", ["差旅住宿标准说明", "年假申请流程"], top_k=2)
        return {"ok": True, "provider": rr.name, "message": f"测试通过（返回 {len(ranked)} 条）"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "provider": rr.name, "message": f"测试失败: {exc}"}


@router.get("/embedding-impact")
def embedding_impact(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return compute_embedding_impact(db)


class RebuildRequest(BaseModel):
    provider: str
    model: str


@router.post("/reindex")
def start_reindex(
    payload: RebuildRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return start_embedding_rebuild(db, payload.provider, payload.model)


@router.get("/reindex-status")
def get_reindex_status(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return reindex_status(db)


@router.post("/reindex/{profile_id}/retry")
def retry_reindex(
    profile_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return retry_rebuild(db, profile_id)
