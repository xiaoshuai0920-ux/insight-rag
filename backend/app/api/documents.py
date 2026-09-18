"""Document API: upload / detail / versions / reindex / chunks / file."""
from __future__ import annotations

import shutil
import tempfile
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Document, DocumentVersion, KnowledgeBase, User
from app.services.document_service import (
    DocumentError,
    chunk_preview,
    create_document_with_version,
    get_document_versions,
    run_document_pipeline,
)
from app.services.embedding_index_service import index_document_version
from app.services.settings_service import get_active_embedding_profile

router = APIRouter(tags=["documents"])


def _get_owned_document(db: Session, user: User, document_id: int) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    kb = db.get(KnowledgeBase, doc.knowledge_base_id)
    if kb is None or kb.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该文档")
    return doc


@router.post("/api/documents/upload")
async def upload_document(
    kb_id: int,
    file: UploadFile,
    version_label: str | None = None,
    file_version: str | None = None,
    effective_date: str | None = None,
    department: str = "",
    category: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None or kb.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="知识库不存在或无权访问")
    file_name = file.filename or "untitled"
    suffix = Path(file_name).suffix.lower()
    if suffix not in {".pdf", ".docx", ".doc", ".md", ".markdown", ".txt"}:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {suffix or '未知'}（支持 PDF / DOCX / Markdown / TXT）",
        )

    # save to temp file first
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        shutil.copyfileobj(file.file, tmp)
        tmp.close()
        from datetime import date as _date

        eff_date = _date.fromisoformat(effective_date) if effective_date else None
        version = create_document_with_version(
            db,
            kb,
            current_user.id,
            file_name,
            tmp.name,
            version_label=version_label or "V1.0",
            file_version=file_version or "1.0",
            effective_date=eff_date,
            department=department,
            category=category or kb.category,
        )
    except DocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        try:
            Path(tmp.name).unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass

    # process asynchronously (real status transitions)
    thread = threading.Thread(
        target=_run_pipeline_thread, args=(version.id,), daemon=True, name=f"doc-pipeline-{version.id}"
    )
    thread.start()

    return {
        "document_id": version.document_id,
        "version_id": version.id,
        "version_label": version.version_label,
        "processing_status": version.processing_status,
        "message": "上传成功，正在处理",
    }


def _run_pipeline_thread(version_id: int) -> None:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        run_document_pipeline(db, version_id)
    finally:
        db.close()


@router.get("/api/documents/{document_id}")
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = _get_owned_document(db, current_user, document_id)
    current = db.get(DocumentVersion, doc.current_version_id) if doc.current_version_id else None
    versions = get_document_versions(db, doc.id)
    return {
        "id": doc.id,
        "title": doc.title,
        "department": doc.department,
        "category": doc.category,
        "knowledge_base_id": doc.knowledge_base_id,
        "current_version": _version_dict(current) if current else None,
        "versions": [_version_dict(v) for v in versions],
    }


@router.delete("/api/documents/{document_id}", status_code=204)
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.rag.retrieval.bm25 import bm25_cache

    doc = _get_owned_document(db, current_user, document_id)
    kb_id = doc.knowledge_base_id
    db.delete(doc)
    db.commit()
    bm25_cache.invalidate([kb_id])
    return None


@router.get("/api/document-versions/{version_id}")
def get_document_version(
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models import Chunk

    version = db.get(DocumentVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="文档版本不存在")
    doc = _get_owned_document(db, current_user, version.document_id)
    preview = chunk_preview(db, version.id)
    child_count = preview["total"]
    parent_count = (
        db.query(Chunk)
        .filter(Chunk.document_version_id == version.id, Chunk.chunk_type == "PARENT")
        .count()
    )
    return {
        **_version_dict(version),
        "document": {"id": doc.id, "title": doc.title, "department": doc.department},
        "parse_overview": {
            "child_chunks": child_count,
            "parent_chunks": parent_count,
        },
        "chunk_preview": preview,
    }


@router.get("/api/document-versions/{version_id}/chunks")
def get_version_chunks(
    version_id: int,
    chunk_type: str = "CHILD",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models import Chunk

    version = db.get(DocumentVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="文档版本不存在")
    _get_owned_document(db, current_user, version.document_id)
    rows = (
        db.query(Chunk)
        .filter(Chunk.document_version_id == version_id, Chunk.chunk_type == chunk_type.upper())
        .order_by(Chunk.id.asc())
        .all()
    )
    return [
        {
            "id": c.id,
            "chunk_type": c.chunk_type,
            "heading_path": c.heading_path,
            "page_number": c.page_number,
            "chunk_index": c.chunk_index,
            "token_count": c.token_count,
            "content": c.content,
            "parent_id": c.parent_id,
        }
        for c in rows
    ]


@router.post("/api/document-versions/{version_id}/reindex")
def reindex_version(
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    version = db.get(DocumentVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="文档版本不存在")
    _get_owned_document(db, current_user, version.document_id)
    profile = get_active_embedding_profile(db)
    if profile is None:
        raise HTTPException(status_code=409, detail="Embedding 模型未就绪，无法重建索引")
    ok = index_document_version(db, version)
    if ok:
        version.processing_status = "READY"
        version.error_message = None
        db.commit()
        return {"status": "READY", "message": "重建索引完成"}
    version.processing_status = "NEEDS_REINDEX"
    version.error_message = "Embedding 模型未就绪，重建失败；请检查设置页"
    db.commit()
    raise HTTPException(status_code=409, detail="Embedding 模型未就绪，重建失败")


@router.get("/api/document-versions/{version_id}/file")
def download_original(
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    version = db.get(DocumentVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="文档版本不存在")
    _get_owned_document(db, current_user, version.document_id)
    path = Path(version.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="原文件不存在")
    return FileResponse(
        str(path), filename=version.file_name, media_type="application/octet-stream"
    )


def _version_dict(v: DocumentVersion) -> dict:
    return {
        "id": v.id,
        "version_label": v.version_label,
        "file_version": v.file_version,
        "file_name": v.file_name,
        "file_type": v.file_type,
        "file_size": v.file_size,
        "sha256": v.sha256[:12] + "…" if v.sha256 else "",
        "effective_date": v.effective_date.isoformat() if v.effective_date else None,
        "expiry_date": v.expiry_date.isoformat() if v.expiry_date else None,
        "processing_status": v.processing_status,
        "lifecycle_status": v.lifecycle_status,
        "error_message": v.error_message,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "updated_at": v.updated_at.isoformat() if v.updated_at else None,
    }
