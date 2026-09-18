"""Full retrieval pipeline orchestration.

Default chat flow:
  Question -> KB scope validation -> ACTIVE/current-version filter
  -> Dense Top10 + BM25 Top10 -> RRF -> Candidate Top12 -> Reranker Top6
  -> Parent recovery -> Parent dedupe -> Final context ~= 4

All numbers are default engineering parameters, adjustable in Retrieval Lab.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models import Chunk, Document, DocumentVersion, KnowledgeBase
from app.providers.reranker.base import RerankerProvider, get_reranker_provider
from app.rag.retrieval.bm25 import bm25_search
from app.rag.retrieval.dense import dense_search
from app.rag.retrieval.rrf import rrf_fuse
from app.services.settings_service import get_active_embedding_profile

MAX_KB_SCOPE = 5
MIN_DENSE_SIMILARITY = 0.35  # below this, evidence is considered insufficient


@dataclass
class RetrievalParams:
    strategy: str = "hybrid_rerank"  # dense / bm25 / hybrid / hybrid_rerank
    dense_top_k: int = 10
    bm25_top_k: int = 10
    rrf_candidate_k: int = 12
    rrf_constant: int = 60
    reranker_top_k: int = 6
    final_context: int = 4

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "dense_top_k": self.dense_top_k,
            "bm25_top_k": self.bm25_top_k,
            "rrf_candidate_k": self.rrf_candidate_k,
            "rrf_constant": self.rrf_constant,
            "reranker_top_k": self.reranker_top_k,
            "final_context": self.final_context,
        }


@dataclass
class StageTiming:
    stage: str
    label: str
    latency_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "label": self.label, "latency_ms": round(self.latency_ms, 1)}


@dataclass
class RetrievedChunk:
    chunk_id: int
    chunk_type: str = "CHILD"
    knowledge_base_id: int = 0
    kb_name: str = ""
    kb_category: str = ""
    document_id: int = 0
    document_title: str = ""
    document_version_id: int = 0
    version_label: str = ""
    file_version: str = ""
    lifecycle_status: str = ""
    effective_date: str | None = None
    heading: str = ""
    heading_path: str = ""
    page_number: int | None = None
    content: str = ""
    parent_id: int | None = None
    parent_content: str | None = None
    # score details (Retrieval Lab only)
    dense_similarity: float | None = None
    bm25_score: float | None = None
    rrf_rank: int | None = None
    rrf_score: float | None = None
    reranker_score: float | None = None
    final_rank: int = 0
    rank_delta: int = 0
    hit_keywords: list[str] = field(default_factory=list)

    def to_lab_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "chunk_type": self.chunk_type,
            "knowledge_base_id": self.knowledge_base_id,
            "kb_name": self.kb_name,
            "document_id": self.document_id,
            "document_title": self.document_title,
            "document_version_id": self.document_version_id,
            "version_label": self.version_label,
            "file_version": self.file_version,
            "lifecycle_status": self.lifecycle_status,
            "heading": self.heading,
            "heading_path": self.heading_path,
            "page_number": self.page_number,
            "content": self.content,
            "parent_id": self.parent_id,
            "parent_content": self.parent_content,
            "dense_similarity": (
                round(self.dense_similarity, 4) if self.dense_similarity is not None else None
            ),
            "bm25_score": round(self.bm25_score, 4) if self.bm25_score is not None else None,
            "rrf_rank": self.rrf_rank,
            "rrf_score": round(self.rrf_score, 4) if self.rrf_score is not None else None,
            "reranker_score": (
                round(self.reranker_score, 4) if self.reranker_score is not None else None
            ),
            "final_rank": self.final_rank,
            "rank_delta": self.rank_delta,
            "hit_keywords": self.hit_keywords,
        }

    def to_citation_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_title": self.document_title,
            "document_version_id": self.document_version_id,
            "version_label": self.version_label,
            "file_version": self.file_version,
            "lifecycle_status": self.lifecycle_status,
            "heading_path": self.heading_path or self.heading,
            "page_number": self.page_number,
            "effective_date": self.effective_date,
            "kb_name": self.kb_name,
            "kb_category": self.kb_category,
            "quote_text": (self.parent_content or self.content)[:400],
        }


@dataclass
class RetrievalResult:
    strategy: str
    hits: list[RetrievedChunk]
    stages: list[StageTiming]
    total_latency_ms: float
    params: dict[str, Any]
    plan: list[dict[str, Any]] = field(default_factory=list)
    reranker_used: bool = False
    reranker_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "hits": [h.to_lab_dict() for h in self.hits],
            "stages": [s.to_dict() for s in self.stages],
            "total_latency_ms": round(self.total_latency_ms, 1),
            "params": self.params,
            "plan": self.plan,
            "reranker_used": self.reranker_used,
            "reranker_error": self.reranker_error,
        }


def validate_kb_scope(db: Session, user_id: int, kb_ids: list[int] | None) -> list[int]:
    """Validate ownership; empty list means ALL knowledge bases."""
    q = db.query(KnowledgeBase.id).filter(KnowledgeBase.user_id == user_id)
    if kb_ids:
        if len(kb_ids) > MAX_KB_SCOPE:
            raise ValueError(f"最多同时选择 {MAX_KB_SCOPE} 个知识库")
        rows = q.filter(KnowledgeBase.id.in_(kb_ids)).all()
        found = {r.id for r in rows}
        missing = [i for i in kb_ids if i not in found]
        if missing:
            raise ValueError("知识库不存在或无权访问")
        return list(kb_ids)
    return [r.id for r in q.all()]


def _query_plan_steps(strategy: str, params: RetrievalParams, reranker_used: bool) -> list[dict]:
    steps = [{"step": "query", "label": "Query", "detail": "用户问题"}]
    if strategy in ("dense", "hybrid", "hybrid_rerank"):
        steps.append({"step": "dense", "label": f"Dense Top {params.dense_top_k}", "detail": "向量检索"})
    if strategy in ("bm25", "hybrid", "hybrid_rerank"):
        steps.append({"step": "bm25", "label": f"BM25 Top {params.bm25_top_k}", "detail": "关键词检索"})
    if strategy in ("hybrid", "hybrid_rerank"):
        steps.append(
            {
                "step": "rrf",
                "label": "RRF 融合排序",
                "detail": f"constant={params.rrf_constant} → Top {params.rrf_candidate_k}",
            }
        )
    if strategy == "hybrid_rerank":
        steps.append(
            {
                "step": "rerank",
                "label": "Reranker 重排",
                "detail": ("Top " + str(params.reranker_top_k)) if reranker_used else "不可用，已跳过",
            }
        )
    steps.append(
        {"step": "parent", "label": "Parent Context", "detail": "回溯父级上下文并去重"}
    )
    steps.append({"step": "final", "label": f"最终 Top {params.final_context}", "detail": "证据输出"})
    return steps


def run_retrieval(
    db: Session,
    user_id: int,
    kb_ids: list[int] | None,
    query: str,
    params: RetrievalParams | None = None,
    reranker: RerankerProvider | None = None,
    query_embedding: list[float] | None = None,
    scope_note: str = "",
) -> RetrievalResult:
    p = params or RetrievalParams()
    stages: list[StageTiming] = []
    errors: list[str] = []

    t0 = time.perf_counter()

    # 1. KB scope validation
    t = time.perf_counter()
    valid_kb_ids = validate_kb_scope(db, user_id, kb_ids)
    stages.append(StageTiming("scope", "知识库范围校验", (time.perf_counter() - t) * 1000))
    if not valid_kb_ids:
        return RetrievalResult(
            strategy=p.strategy,
            hits=[],
            stages=stages,
            total_latency_ms=(time.perf_counter() - t0) * 1000,
            params=p.to_dict(),
            plan=_query_plan_steps(p.strategy, p, False),
            reranker_error="没有可检索的知识库",
        )

    # 2. Embedding (dense path)
    query_vec: list[float] | None = query_embedding
    active_profile = None
    if p.strategy in ("dense", "hybrid", "hybrid_rerank"):
        t = time.perf_counter()
        active_profile = get_active_embedding_profile(db)
        if active_profile is None:
            errors.append("Embedding 索引未就绪，Dense 检索不可用")
        elif query_vec is None:
            from app.providers.embedding.base import EmbeddingError
            from app.providers.embedding.base import get_embedding_provider

            try:
                provider = get_embedding_provider()
                query_vec = provider.embed_query(query)
            except EmbeddingError as exc:
                errors.append(f"向量化失败: {exc}")
                query_vec = None
        stages.append(
            StageTiming("embed", "Query 向量化", (time.perf_counter() - t) * 1000)
        )

    hits_by_id: dict[int, RetrievedChunk] = {}
    dense_hits = []
    bm25_hits = []

    # 3. Dense search
    if p.strategy in ("dense", "hybrid", "hybrid_rerank") and active_profile and query_vec:
        t = time.perf_counter()
        from app.rag.retrieval.dense import DenseHit

        dense_hits: list[DenseHit] = dense_search(
            db, valid_kb_ids, query_vec, active_profile.id, top_k=p.dense_top_k
        )
        stages.append(StageTiming("dense", f"Dense Top {p.dense_top_k}", (time.perf_counter() - t) * 1000))

    # 4. BM25 search
    if p.strategy in ("bm25", "hybrid", "hybrid_rerank"):
        t = time.perf_counter()
        bm25_hits = bm25_search(db, valid_kb_ids, query, top_k=p.bm25_top_k)
        stages.append(StageTiming("bm25", f"BM25 Top {p.bm25_top_k}", (time.perf_counter() - t) * 1000))

    # 5. Fusion / selection
    t = time.perf_counter()
    if p.strategy in ("hybrid", "hybrid_rerank"):
        candidates = rrf_fuse(dense_hits, bm25_hits, rrf_constant=p.rrf_constant,
                              candidate_k=p.rrf_candidate_k)
    elif p.strategy == "dense":
        candidates = []
        for rank, h in enumerate(dense_hits, start=1):
            from app.rag.retrieval.rrf import RrfCandidate

            candidates.append(
                RrfCandidate(
                    chunk_id=h.chunk_id, rrf_score=h.similarity, dense_rank=rank,
                    dense_similarity=h.similarity, rrf_rank=rank,
                )
            )
    else:  # bm25
        from app.rag.retrieval.rrf import RrfCandidate

        candidates = [
            RrfCandidate(
                chunk_id=h.chunk_id, rrf_score=h.score, bm25_rank=rank,
                bm25_score=h.score, rrf_rank=rank,
            )
            for rank, h in enumerate(bm25_hits, start=1)
        ]
    stages.append(StageTiming("fusion", "候选合并", (time.perf_counter() - t) * 1000))

    # 6. Hydrate chunk rows (respect CURRENT+READY filter for chat usage)
    t = time.perf_counter()
    chunk_ids = [c.chunk_id for c in candidates]
    chunk_rows: dict[int, Chunk] = {}
    if chunk_ids:
        rows = (
            db.query(Chunk)
            .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
            .filter(Chunk.id.in_(chunk_ids))
            .filter(
                DocumentVersion.processing_status == "READY",
                DocumentVersion.lifecycle_status == "CURRENT",
            )
            .all()
        )
        chunk_rows = {r.id: r for r in rows}
    # effective-date filter: only versions whose effective_date <= today (if set)
    from datetime import date as _date

    kb_rows = {kb.id: kb for kb in db.query(KnowledgeBase).filter(KnowledgeBase.id.in_(valid_kb_ids))}
    doc_rows: dict[int, Document] = {}
    if chunk_rows:
        doc_ids = {c.document_version_id for c in chunk_rows.values()}
        dvs = db.query(DocumentVersion).filter(DocumentVersion.id.in_(doc_ids)).all()
        dv_map = {d.id: d for d in dvs}
        docs = db.query(Document).filter(Document.id.in_([d.document_id for d in dvs])).all()
        doc_rows = {d.id: d for d in docs}
    else:
        dv_map = {}

    today = _date.today()
    for c in candidates:
        chunk = chunk_rows.get(c.chunk_id)
        if chunk is None:
            continue
        dv = dv_map.get(chunk.document_version_id)
        if dv is None or dv.document_id is None:
            continue
        if dv.effective_date and dv.effective_date > today:
            continue
        doc = doc_rows.get(dv.document_id)
        if doc is None:
            continue
        kb = kb_rows.get(chunk.knowledge_base_id)
        hits_by_id[c.chunk_id] = RetrievedChunk(
            chunk_id=c.chunk_id,
            knowledge_base_id=chunk.knowledge_base_id,
            kb_name=kb.name if kb else "",
            kb_category=kb.category if kb else "",
            document_id=doc.id,
            document_title=doc.title,
            document_version_id=dv.id,
            version_label=dv.version_label,
            file_version=dv.file_version,
            lifecycle_status=dv.lifecycle_status,
            effective_date=dv.effective_date.isoformat() if dv.effective_date else None,
            heading=chunk.heading,
            heading_path=chunk.heading_path,
            page_number=chunk.page_number,
            content=chunk.content,
            parent_id=chunk.parent_id,
            dense_similarity=c.dense_similarity,
            bm25_score=c.bm25_score,
            rrf_rank=c.rrf_rank,
            rrf_score=c.rrf_score,
            hit_keywords=[],
        )
    stages.append(StageTiming("hydrate", "加载片段信息", (time.perf_counter() - t) * 1000))

    hydrated = [h for h in (hits_by_id.get(c.chunk_id) for c in candidates) if h is not None]

    # 7. Reranker
    reranker_used = False
    reranker_error: str | None = None
    if p.strategy == "hybrid_rerank" and hydrated:
        t = time.perf_counter()
        rr = reranker or get_reranker_provider()
        if rr.is_available():
            try:
                ranked = rr.rerank(query, [h.content for h in hydrated], top_k=p.reranker_top_k)
                for h in hydrated:
                    h.reranker_score = None
                reranked: list[RetrievedChunk] = []
                for idx, score in ranked:
                    hydrated[idx].reranker_score = score
                    reranked.append(hydrated[idx])
                hydrated = reranked
                reranker_used = True
            except Exception as exc:
                reranker_error = f"Reranker 执行失败，已按融合排序继续: {exc}"
        else:
            reranker_error = "Reranker 模型未就绪，已按融合排序继续"
        stages.append(StageTiming("rerank", "Reranker 重排", (time.perf_counter() - t) * 1000))

    # 8. Parent recovery + dedupe
    t = time.perf_counter()
    parent_ids = [h.parent_id for h in hydrated if h.parent_id]
    parent_map: dict[int, Chunk] = {}
    if parent_ids:
        prows = db.query(Chunk).filter(Chunk.id.in_(parent_ids)).all()
        parent_map = {r.id: r for r in prows}
    final_hits: list[RetrievedChunk] = []
    seen_parents: set[int | None] = set()
    for h in hydrated:
        if h.parent_id is not None:
            if h.parent_id in seen_parents:
                # keep the higher-ranked child of the same parent as an alternate
                continue
            seen_parents.add(h.parent_id)
            parent = parent_map.get(h.parent_id)
            if parent is not None:
                h.parent_content = parent.content
        if len(final_hits) >= max(p.final_context, 1):
            # stop after final_context, but allow a couple of alternates
            if len(final_hits) >= p.final_context + 2:
                break
        final_hits.append(h)
        if len(final_hits) >= p.final_context:
            # append up to 2 alternates from same/different parents for citation depth
            continue
    if len(final_hits) > p.final_context + 2:
        final_hits = final_hits[: p.final_context + 2]
    # final ranks + delta (relative to RRF rank when present)
    for i, h in enumerate(final_hits, start=1):
        h.final_rank = i
        if h.rrf_rank:
            h.rank_delta = h.rrf_rank - i  # positive = moved up
    stages.append(StageTiming("parent", "Parent 回溯与去重", (time.perf_counter() - t) * 1000))

    total_ms = (time.perf_counter() - t0) * 1000
    plan = _query_plan_steps(p.strategy, p, reranker_used)
    result = RetrievalResult(
        strategy=p.strategy,
        hits=final_hits,
        stages=stages,
        total_latency_ms=total_ms,
        params=p.to_dict(),
        plan=plan,
        reranker_used=reranker_used,
        reranker_error=reranker_error,
    )
    if errors:
        result.reranker_error = "; ".join(errors) if not result.reranker_error else result.reranker_error
    return result
