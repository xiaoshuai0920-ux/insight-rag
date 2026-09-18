"""Unified statistics service — the ONLY source of numbers for all pages.

Definitions (see master spec §7):
- knowledge_bases: KBs owned by current user
- total_documents: logical documents (not versions)
- available_documents: current version READY + CURRENT
- retrievable_chunks: CHILD chunks from CURRENT+READY versions under ACTIVE profile
- processing_documents: current version in PARSING/CHUNKING/INDEXING
- failed_documents: current version FAILED
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Chunk,
    Conversation,
    Document,
    DocumentVersion,
    KnowledgeBase,
    Message,
)
from app.services.settings_service import get_active_embedding_profile


def kb_aggregate_status(db: Session, kb_id: int, has_docs: bool) -> str:
    """Aggregate KB status from current versions (see spec §8.2)."""
    if not has_docs:
        return "EMPTY"
    rows = (
        db.query(DocumentVersion.processing_status)
        .join(Document, Document.current_version_id == DocumentVersion.id)
        .filter(Document.knowledge_base_id == kb_id)
        .all()
    )
    statuses = [r.processing_status for r in rows]
    if not statuses:
        return "EMPTY"
    processing = any(s in ("PARSING", "CHUNKING", "INDEXING", "UPLOADED") for s in statuses)
    failed = any(s == "FAILED" for s in statuses)
    ready = any(s == "READY" for s in statuses)
    if processing and (ready or failed):
        return "UPDATING"
    if processing:
        return "UPDATING"
    if failed and ready:
        return "PARTIAL"
    if failed:
        return "PARTIAL"
    if all(s == "READY" for s in statuses):
        return "READY"
    return "PARTIAL"


def kb_stats(db: Session, kb_id: int) -> dict[str, Any]:
    total_docs = (
        db.query(func.count(Document.id)).filter(Document.knowledge_base_id == kb_id).scalar() or 0
    )
    available_docs = (
        db.query(func.count(Document.id))
        .join(DocumentVersion, Document.current_version_id == DocumentVersion.id)
        .filter(
            Document.knowledge_base_id == kb_id,
            DocumentVersion.processing_status == "READY",
            DocumentVersion.lifecycle_status == "CURRENT",
        )
        .scalar()
    ) or 0
    processing_docs = (
        db.query(func.count(Document.id))
        .join(DocumentVersion, Document.current_version_id == DocumentVersion.id)
        .filter(
            Document.knowledge_base_id == kb_id,
            DocumentVersion.processing_status.in_(["PARSING", "CHUNKING", "INDEXING", "UPLOADED"]),
        )
        .scalar()
    ) or 0
    failed_docs = (
        db.query(func.count(Document.id))
        .join(DocumentVersion, Document.current_version_id == DocumentVersion.id)
        .filter(
            Document.knowledge_base_id == kb_id,
            DocumentVersion.processing_status == "FAILED",
        )
        .scalar()
    ) or 0
    retrievable_chunks = (
        db.query(func.count(Chunk.id))
        .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
        .filter(
            Chunk.knowledge_base_id == kb_id,
            Chunk.chunk_type == "CHILD",
            DocumentVersion.lifecycle_status == "CURRENT",
            DocumentVersion.processing_status == "READY",
        )
        .scalar()
    ) or 0
    return {
        "total_documents": total_docs,
        "available_documents": available_docs,
        "processing_documents": processing_docs,
        "failed_documents": failed_docs,
        "retrievable_chunks": retrievable_chunks,
        "status": kb_aggregate_status(db, kb_id, total_docs > 0),
    }


def user_dashboard_stats(db: Session, user_id: int) -> dict[str, Any]:
    kb_ids = [
        r.id for r in db.query(KnowledgeBase.id).filter(KnowledgeBase.user_id == user_id).all()
    ]
    total_docs = 0
    available_docs = 0
    processing_docs = 0
    retrievable_chunks = 0
    for kb_id in kb_ids:
        s = kb_stats(db, kb_id)
        total_docs += s["total_documents"]
        available_docs += s["available_documents"]
        processing_docs += s["processing_documents"]
        retrievable_chunks += s["retrievable_chunks"]
    return {
        "knowledge_bases": len(kb_ids),
        "total_documents": total_docs,
        "available_documents": available_docs,
        "retrievable_chunks": retrievable_chunks,
        "processing_documents": processing_docs,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def recent_knowledge_bases(db: Session, user_id: int, limit: int = 4) -> list[dict[str, Any]]:
    kbs = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.user_id == user_id)
        .order_by(KnowledgeBase.updated_at.desc())
        .limit(limit)
        .all()
    )
    out = []
    for kb in kbs:
        s = kb_stats(db, kb.id)
        out.append(
            {
                "id": kb.id,
                "name": kb.name,
                "description": kb.description,
                "category": kb.category,
                "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
                **s,
            }
        )
    return out


def recent_conversations(db: Session, user_id: int, limit: int = 5) -> list[dict[str, Any]]:
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .all()
    )
    out = []
    for conv in convs:
        first_user_msg = (
            db.query(Message)
            .filter(Message.conversation_id == conv.id, Message.role == "USER")
            .order_by(Message.created_at.asc())
            .first()
        )
        # which KBs were used (snapshot from latest user message)
        latest_user_msg = (
            db.query(Message)
            .filter(Message.conversation_id == conv.id, Message.role == "USER")
            .order_by(Message.created_at.desc())
            .first()
        )
        kb_names: list[str] = []
        if latest_user_msg and latest_user_msg.retrieval_meta:
            kb_ids = latest_user_msg.retrieval_meta.get("kb_scope", [])
            if kb_ids:
                rows = db.query(KnowledgeBase).filter(KnowledgeBase.id.in_(kb_ids)).all()
                kb_names = [r.name for r in rows]
        out.append(
            {
                "id": conv.id,
                "title": conv.title,
                "question": (first_user_msg.content[:60] if first_user_msg else conv.title),
                "kb_names": kb_names or ["全部知识库"],
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            }
        )
    return out
