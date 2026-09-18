"""Knowledge base API: CRUD + stats + documents."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Document, DocumentVersion, KnowledgeBase, User
from app.rag.retrieval.bm25 import bm25_cache
from app.services.stats_service import kb_stats

router = APIRouter(prefix="/api/knowledge-bases", tags=["knowledge-bases"])


class KBCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=500)
    category: str = Field(default="general", max_length=64)


def _get_owned_kb(db: Session, user: User, kb_id: int) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None or kb.user_id != user.id:
        raise HTTPException(status_code=404, detail="知识库不存在或无权访问")
    return kb


@router.get("")
def list_knowledge_bases(
    q: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(KnowledgeBase).filter(KnowledgeBase.user_id == current_user.id)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            (KnowledgeBase.name.ilike(like)) | (KnowledgeBase.description.ilike(like))
        )
    kbs = query.order_by(KnowledgeBase.updated_at.desc()).all()
    return [
        {
            "id": kb.id,
            "name": kb.name,
            "description": kb.description,
            "category": kb.category,
            "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
            **kb_stats(db, kb.id),
        }
        for kb in kbs
    ]


@router.post("", status_code=201)
def create_knowledge_base(
    payload: KBCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kb = KnowledgeBase(
        user_id=current_user.id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        category=payload.category,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return {
        "id": kb.id,
        "name": kb.name,
        "description": kb.description,
        "category": kb.category,
        "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
        **kb_stats(db, kb.id),
    }


@router.get("/{kb_id}")
def get_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kb = _get_owned_kb(db, current_user, kb_id)
    return {
        "id": kb.id,
        "name": kb.name,
        "description": kb.description,
        "category": kb.category,
        "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
        **kb_stats(db, kb.id),
    }


@router.put("/{kb_id}")
def update_knowledge_base(
    kb_id: int,
    payload: KBCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kb = _get_owned_kb(db, current_user, kb_id)
    kb.name = payload.name.strip() or kb.name
    kb.description = payload.description.strip()
    kb.category = payload.category
    db.commit()
    db.refresh(kb)
    return {
        "id": kb.id,
        "name": kb.name,
        "description": kb.description,
        "category": kb.category,
        "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
        **kb_stats(db, kb.id),
    }


@router.delete("/{kb_id}", status_code=204)
def delete_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kb = _get_owned_kb(db, current_user, kb_id)
    db.delete(kb)
    db.commit()
    bm25_cache.invalidate([kb_id])
    return None


@router.get("/{kb_id}/stats")
def get_kb_stats(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kb = _get_owned_kb(db, current_user, kb_id)
    return kb_stats(db, kb.id)


@router.get("/{kb_id}/documents")
def list_kb_documents(
    kb_id: int,
    q: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kb = _get_owned_kb(db, current_user, kb_id)
    query = db.query(Document).filter(Document.knowledge_base_id == kb.id)
    if q.strip():
        query = query.filter(Document.title.ilike(f"%{q.strip()}%"))
    docs = query.order_by(Document.updated_at.desc()).all()
    out = []
    for doc in docs:
        current = db.get(DocumentVersion, doc.current_version_id) if doc.current_version_id else None
        version_count = (
            db.query(DocumentVersion).filter(DocumentVersion.document_id == doc.id).count()
        )
        out.append(
            {
                "id": doc.id,
                "title": doc.title,
                "department": doc.department,
                "category": doc.category,
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
                "current_version": {
                    "id": current.id,
                    "version_label": current.version_label,
                    "file_version": current.file_version,
                    "file_name": current.file_name,
                    "file_type": current.file_type,
                    "file_size": current.file_size,
                    "effective_date": current.effective_date.isoformat() if current.effective_date else None,
                    "processing_status": current.processing_status,
                    "lifecycle_status": current.lifecycle_status,
                    "error_message": current.error_message,
                    "updated_at": current.updated_at.isoformat() if current.updated_at else None,
                }
                if current
                else None,
                "version_count": version_count,
            }
        )
    return out
