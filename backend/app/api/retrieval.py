"""Retrieval Lab API: run / compare."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.rag.retrieval.pipeline import (
    MAX_KB_SCOPE,
    RetrievalParams,
    RetrievalResult,
    run_retrieval,
)

router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])


class RetrievalRunRequest(BaseModel):
    kb_ids: list[int] | None = None
    question: str = Field(min_length=1, max_length=500)
    strategy: str = Field(default="hybrid_rerank")
    dense_top_k: int = Field(default=10, ge=1, le=50)
    bm25_top_k: int = Field(default=10, ge=1, le=50)
    rrf_candidate_k: int = Field(default=12, ge=1, le=100)
    rrf_constant: int = Field(default=60, ge=1, le=200)
    reranker_top_k: int = Field(default=6, ge=1, le=50)
    final_context: int = Field(default=4, ge=1, le=20)


def _params_from(req: RetrievalRunRequest) -> RetrievalParams:
    return RetrievalParams(
        strategy=req.strategy,
        dense_top_k=req.dense_top_k,
        bm25_top_k=req.bm25_top_k,
        rrf_candidate_k=req.rrf_candidate_k,
        rrf_constant=req.rrf_constant,
        reranker_top_k=req.reranker_top_k,
        final_context=req.final_context,
    )


@router.post("/run")
def run_retrieval_lab(
    payload: RetrievalRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.strategy not in ("dense", "bm25", "hybrid", "hybrid_rerank"):
        raise HTTPException(status_code=400, detail=f"未知策略: {payload.strategy}")
    try:
        result: RetrievalResult = run_retrieval(db, current_user.id, payload.kb_ids, payload.question, _params_from(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    out = result.to_dict()
    # annotation clarity: each score field carries its own type name
    out["score_types"] = {
        "dense_similarity": "Dense Similarity (cosine)",
        "bm25_score": "BM25 Score",
        "rrf_rank": "RRF Rank",
        "reranker_score": "Reranker Score",
    }
    return out


@router.post("/compare")
def compare_strategies(
    payload: RetrievalRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base = _params_from(payload)
    dense_params = RetrievalParams(
        strategy="dense",
        dense_top_k=base.dense_top_k,
        bm25_top_k=base.bm25_top_k,
        rrf_candidate_k=base.rrf_candidate_k,
        rrf_constant=base.rrf_constant,
        reranker_top_k=base.reranker_top_k,
        final_context=base.final_context,
    )
    try:
        dense = run_retrieval(db, current_user.id, payload.kb_ids, payload.question, dense_params)
        hybrid = run_retrieval(db, current_user.id, payload.kb_ids, payload.question, base)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"dense": dense.to_dict(), "hybrid": hybrid.to_dict()}
