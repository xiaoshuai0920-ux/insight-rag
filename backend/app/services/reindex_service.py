"""Embedding profile switching with fail-safe rebuild loop.

Switch flow:
  user picks new embedding -> compute impact -> confirm "replace & rebuild"
  -> create BUILDING profile -> background-embed all valid CHILD chunks
  -> old ACTIVE profile keeps serving -> on success atomically switch ACTIVE
  -> old profile becomes INACTIVE; on failure new profile = FAILED, old stays.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import Chunk, Document, DocumentVersion, EmbeddingProfile
from app.services.settings_service import (
    get_active_embedding_profile,
    get_setting,
    set_setting,
)


def compute_embedding_impact(db: Session) -> dict[str, Any]:
    """Affected KBs / documents / chunks for the embedding switch warning."""
    active = get_active_embedding_profile(db)
    from app.models import KnowledgeBase

    kb_rows = (
        db.query(
            KnowledgeBase.id,
            KnowledgeBase.name,
            Document.id.label("doc_id"),
        )
        .join(Document, Document.knowledge_base_id == KnowledgeBase.id)
        .join(DocumentVersion, DocumentVersion.document_id == Document.id)
        .filter(
            DocumentVersion.processing_status.in_(["READY", "NEEDS_REINDEX"]),
            DocumentVersion.lifecycle_status == "CURRENT",
        )
        .all()
    )
    kb_map: dict[int, dict[str, Any]] = {}
    doc_ids: set[int] = set()
    for row in kb_rows:
        kb_map.setdefault(row.id, {"id": row.id, "name": row.name, "documents": 0})
        kb_map[row.id]["documents"] += 1
        doc_ids.add(row.doc_id)

    chunk_count = 0
    if doc_ids:
        chunk_count = (
            db.query(Chunk)
            .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
            .filter(
                DocumentVersion.document_id.in_(list(doc_ids)),
                DocumentVersion.lifecycle_status == "CURRENT",
                DocumentVersion.processing_status.in_(["READY", "NEEDS_REINDEX"]),
                Chunk.chunk_type == "CHILD",
            )
            .count()
        )
    return {
        "current_profile": _profile_dict(active),
        "affected_knowledge_bases": len(kb_map),
        "affected_documents": len(doc_ids),
        "affected_chunks": chunk_count,
        "kb_list": sorted(kb_map.values(), key=lambda k: k["name"]),
    }


def start_embedding_rebuild(
    db: Session,
    provider_name: str,
    model_name: str,
) -> dict[str, Any]:
    """Create a BUILDING profile and kick off the background rebuild."""
    from app.db.session import SessionLocal
    from app.services.embedding_index_service import ensure_default_profile

    old_active = get_active_embedding_profile(db)
    if old_active is not None and old_active.provider == provider_name and old_active.model_name == model_name:
        return {"status": "noop", "message": "新配置与当前 ACTIVE 模型相同，无需重建", "profile": _profile_dict(old_active)}

    profile = EmbeddingProfile(
        provider=provider_name,
        model_name=model_name,
        dimension=None,
        status="BUILDING",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    thread = threading.Thread(
        target=_rebuild_worker,
        args=(profile.id, old_active.id if old_active else None),
        daemon=True,
        name=f"embedding-rebuild-{profile.id}",
    )
    thread.start()
    ensure_default_profile.__doc__  # keep import used
    return {"status": "started", "profile": _profile_dict(profile)}


def _rebuild_worker(profile_id: int, old_profile_id: int | None) -> None:
    """Background worker: embed everything, then atomically switch profiles."""
    from app.db.session import SessionLocal
    from app.services.embedding_index_service import index_document_version

    db = SessionLocal()
    try:
        profile = db.get(EmbeddingProfile, profile_id)
        if profile is None:
            return
        from app.providers.embedding.base import get_embedding_provider

        provider = get_embedding_provider()
        try:
            dim = provider.get_dimension()
        except Exception:
            dim = None
        if dim is None:
            profile.status = "FAILED"
            profile.error_message = "Embedding 模型不可用（无法生成测试向量），旧索引继续服务"
            db.commit()
            return
        profile.dimension = dim

        version_rows = (
            db.query(DocumentVersion.id)
            .filter(
                DocumentVersion.lifecycle_status == "CURRENT",
                DocumentVersion.processing_status.in_(["READY", "NEEDS_REINDEX"]),
            )
            .all()
        )
        version_ids = [r.id for r in version_rows]
        failed = 0
        for vid in version_ids:
            version = db.get(DocumentVersion, vid)
            if version is None:
                continue
            ok = index_document_version(db, version, profile=profile)
            if not ok:
                failed += 1

        if failed and failed == len(version_ids):
            profile.status = "FAILED"
            profile.error_message = "全部文档向量重建失败，旧索引继续服务"
            db.commit()
            return

        # atomic switch
        now = datetime.now(timezone.utc)
        if old_profile_id:
            old = db.get(EmbeddingProfile, old_profile_id)
            if old is not None:
                old.status = "INACTIVE"
        profile.status = "ACTIVE"
        profile.activated_at = now
        profile.error_message = None
        set_setting(db, "active_embedding_profile_id", profile.id)

        # versions that were NEEDS_REINDEX can become READY now
        if failed == 0:
            db.query(DocumentVersion).filter(
                DocumentVersion.lifecycle_status == "CURRENT",
                DocumentVersion.processing_status == "NEEDS_REINDEX",
            ).update(
                {DocumentVersion.processing_status: "READY"},
                synchronize_session=False,
            )
        db.commit()

        # invalidate BM25 cache (chunk set unchanged, but keep clean)
        from app.rag.retrieval.bm25 import bm25_cache

        bm25_cache.invalidate()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        profile = db.get(EmbeddingProfile, profile_id)
        if profile is not None:
            profile.status = "FAILED"
            profile.error_message = f"重建失败: {exc}（旧索引继续服务）"
            db.commit()
    finally:
        db.close()


def reindex_status(db: Session) -> dict[str, Any]:
    active = get_active_embedding_profile(db)
    building = (
        db.query(EmbeddingProfile)
        .filter(EmbeddingProfile.status.in_(["BUILDING", "FAILED"]))
        .order_by(EmbeddingProfile.id.desc())
        .first()
    )
    total_versions = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.lifecycle_status == "CURRENT",
            DocumentVersion.processing_status.in_(["READY", "NEEDS_REINDEX"]),
        )
        .count()
    )
    done = 0
    if building is not None and building.status == "BUILDING" and active is not None:
        from app.models import ChunkEmbedding

        version_ids = [
            r.id
            for r in db.query(DocumentVersion.id)
            .filter(
                DocumentVersion.lifecycle_status == "CURRENT",
                DocumentVersion.processing_status.in_(["READY", "NEEDS_REINDEX"]),
            )
            .all()
        ]
        if version_ids:
            done = (
                db.query(ChunkEmbedding)
                .join(Chunk, Chunk.id == ChunkEmbedding.chunk_id)
                .filter(
                    ChunkEmbedding.embedding_profile_id == building.id,
                    Chunk.document_version_id.in_(version_ids),
                )
                .count()
            )
    return {
        "active_profile": _profile_dict(active),
        "rebuilding_profile": _profile_dict(building),
        "total_versions": total_versions,
        "embedded_versions_done": done,
    }


def retry_rebuild(db: Session, profile_id: int) -> dict[str, Any]:
    profile = db.get(EmbeddingProfile, profile_id)
    if profile is None:
        return {"status": "error", "message": "重建任务不存在"}
    if profile.status != "FAILED":
        return {"status": "error", "message": "仅失败任务可重试"}
    active = get_active_embedding_profile(db)
    profile.status = "BUILDING"
    profile.error_message = None
    db.commit()
    thread = threading.Thread(
        target=_rebuild_worker,
        args=(profile.id, active.id if active else None),
        daemon=True,
    )
    thread.start()
    return {"status": "started", "profile": _profile_dict(profile)}


def _profile_dict(p: EmbeddingProfile | None) -> dict[str, Any] | None:
    if p is None:
        return None
    return {
        "id": p.id,
        "provider": p.provider,
        "model_name": p.model_name,
        "dimension": p.dimension,
        "status": p.status,
        "error_message": p.error_message,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "activated_at": p.activated_at.isoformat() if p.activated_at else None,
    }
