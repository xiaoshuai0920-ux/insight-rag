"""Evaluation API: run golden dataset, list runs."""
from __future__ import annotations

import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import EvaluationRun, User
from app.rag.evaluation.runner import evaluate_strategy, load_golden_dataset

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


class EvaluationRunRequest(BaseModel):
    strategy: str = "hybrid"
    kb_ids: list[int] | None = None


@router.post("/run")
def run_evaluation(
    payload: EvaluationRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.strategy not in ("dense", "bm25", "hybrid", "hybrid_rerank"):
        raise HTTPException(status_code=400, detail=f"未知策略: {payload.strategy}")
    cases = load_golden_dataset()
    if not cases:
        raise HTTPException(
            status_code=404, detail="未找到 Golden Dataset（demo-data/golden-dataset.json）"
        )
    run, _items = evaluate_strategy(
        db, current_user.id, payload.strategy, cases, kb_scope_ids=payload.kb_ids
    )
    return _run_dict(run)


@router.get("/runs")
def list_runs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    runs = db.query(EvaluationRun).order_by(EvaluationRun.id.desc()).limit(20).all()
    return [_run_dict(r) for r in runs]


@router.get("/runs/{run_id}")
def get_run(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = db.get(EvaluationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="评测记录不存在")
    return _run_dict(run)


def _run_dict(run: EvaluationRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "strategy": run.strategy,
        "status": run.status,
        "total_cases": run.total_cases,
        "recall_at_5": run.recall_at_5,
        "mrr": run.mrr,
        "avg_latency_ms": run.avg_latency_ms,
        "error_message": run.error_message,
        "detail": run.detail,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }
