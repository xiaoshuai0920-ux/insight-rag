"""Golden Dataset evaluation runner.

Metrics (all computed from real retrieval runs):
- Recall@5: expected document appears in top-5 results
- MRR: 1/rank of first expected-document hit
- Average retrieval latency

Strategies compared: dense / hybrid / hybrid_rerank.
NO fabricated numbers: if embedding is unavailable, dense strategies are
reported as failed/skipped with the reason.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models import Document, EvaluationRun, EvaluationRunItem
from app.rag.retrieval.pipeline import RetrievalParams, run_retrieval

# runner.py lives at backend/app/rag/evaluation/runner.py
# -> 5 levels up is the project root (InsightRAG/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
DEMO_DIR = PROJECT_ROOT / "demo-data"


def load_golden_dataset() -> list[dict[str, Any]]:
    path = DEMO_DIR / "golden-dataset.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("cases", [])


def _normalize(s: str) -> str:
    return (s or "").strip().lower()


def evaluate_strategy(
    db: Session,
    user_id: int,
    strategy: str,
    cases: list[dict[str, Any]],
    kb_scope_ids: list[int] | None = None,
) -> tuple[EvaluationRun, list[dict[str, Any]]]:
    run = EvaluationRun(strategy=strategy, status="RUNNING", total_cases=len(cases))
    db.add(run)
    db.commit()
    db.refresh(run)

    items: list[dict[str, Any]] = []
    reciprocal_sum = 0.0
    hits_at_5 = 0
    latencies: list[float] = []
    errors: list[str] = []

    for case in cases:
        question = case["question"]
        expected_doc = _normalize(case.get("expected_document", ""))
        params = RetrievalParams(
            strategy=strategy,
            dense_top_k=10,
            bm25_top_k=10,
            rrf_candidate_k=12,
            rrf_constant=60,
            reranker_top_k=6,
            final_context=5,
        )
        try:
            t0 = time.perf_counter()
            result = run_retrieval(
                db,
                user_id,
                kb_scope_ids,
                question,
                params,
                query_embedding=None,
            )
            latency = (time.perf_counter() - t0) * 1000
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{question}: {exc}")
            items.append(
                {
                    "question": question,
                    "expected_document": expected_doc,
                    "hit": False,
                    "rank": None,
                    "latency_ms": None,
                    "top_documents": [],
                    "error": str(exc),
                }
            )
            continue

        latencies.append(latency)
        rank: int | None = None
        top_docs: list[str] = []
        for h in result.hits:
            top_docs.append(h.document_title)
            if rank is None and expected_doc and _normalize(h.document_title) == expected_doc:
                rank = h.final_rank
        hit = rank is not None
        if hit:
            hits_at_5 += 1
            reciprocal_sum += 1.0 / rank
        items.append(
            {
                "question": question,
                "expected_document": case.get("expected_document", ""),
                "hit": hit,
                "rank": rank,
                "latency_ms": round(latency, 1),
                "top_documents": top_docs[:5],
            }
        )

    total = max(len(cases), 1)
    recall = hits_at_5 / total if cases else None
    mrr = (reciprocal_sum / total) if cases else None
    avg_latency = (sum(latencies) / len(latencies)) if latencies else None

    run.status = "DONE" if not (errors and len(errors) == len(cases)) else "FAILED"
    run.recall_at_5 = recall
    run.mrr = mrr
    run.avg_latency_ms = avg_latency
    run.error_message = "; ".join(errors[:3]) if errors else None
    run.detail = {
        "cases": items,
        "note": "结果来自真实检索运行；如 Embedding/Reranker 未就绪，对应策略会失败并注明原因。",
    }
    db.commit()
    db.refresh(run)
    return run, items
