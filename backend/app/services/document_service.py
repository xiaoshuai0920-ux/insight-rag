"""Document upload + processing pipeline.

Pipeline: Upload -> save file -> PARSING -> CHUNKING -> INDEXING -> READY
Real status transitions only — never fake READY right after upload.
"""
from __future__ import annotations

import hashlib
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Chunk, Document, DocumentVersion, KnowledgeBase
from app.rag.chunking.chunker import (
    DEFAULT_CHILD_OVERLAP,
    DEFAULT_CHILD_TOKENS,
    DEFAULT_PARENT_TOKENS,
    build_parent_child_chunks,
)
from app.rag.chunking.tokens import estimate_tokens
from app.rag.parsing.base import DocumentParser, ScanPdfError, get_parser
from app.rag.retrieval.bm25 import bm25_cache

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".md", ".markdown", ".txt"}


class DocumentError(Exception):
    pass


def _user_upload_dir(user_id: int, kb_id: int, document_id: int, version_id: int) -> Path:
    base = Path(settings.UPLOAD_DIR) / str(user_id) / str(kb_id) / str(document_id) / str(version_id)
    base.mkdir(parents=True, exist_ok=True)
    return base


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def compute_document_title(file_name: str) -> str:
    return Path(file_name).stem


def create_document_with_version(
    db: Session,
    kb: KnowledgeBase,
    user_id: int,
    file_name: str,
    tmp_file_path: str,
    version_label: str = "V1.0",
    file_version: str = "1.0",
    effective_date: date | None = None,
    expiry_date: date | None = None,
    lifecycle_status: str = "CURRENT",
    department: str = "",
    category: str = "",
) -> DocumentVersion:
    """Create logical document (or new version of existing document) + save file."""
    src = Path(tmp_file_path)
    suffix = src.suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise DocumentError(f"不支持的文件格式: {suffix or file_name}（支持 PDF / DOCX / Markdown / TXT）")
    size = src.stat().st_size
    if size > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise DocumentError(f"文件超过 {settings.MAX_UPLOAD_MB}MB 上限")

    # logical document: reuse when same title exists in this KB (new version)
    title = compute_document_title(file_name)
    doc = (
        db.query(Document)
        .filter(Document.knowledge_base_id == kb.id, Document.title == title)
        .first()
    )
    if doc is None:
        doc = Document(
            knowledge_base_id=kb.id, title=title, department=department, category=category
        )
        db.add(doc)
        db.flush()
    else:
        # bump version label for the same logical document
        existing = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == doc.id)
            .order_by(DocumentVersion.id.desc())
            .first()
        )
        if existing is not None:
            try:
                major, minor = existing.version_label.lstrip("Vv").split(".")
                version_label = f"V{int(major) + 1}.0"
                file_version = f"{int(float(existing.file_version or 1) ) + 1}.0"
            except ValueError:
                pass
            # historical versions
            existing.lifecycle_status = "HISTORICAL"

    version = DocumentVersion(
        document_id=doc.id,
        version_label=version_label,
        file_version=file_version,
        file_name=file_name,
        file_path="",
        file_type=suffix.lstrip("."),
        file_size=size,
        sha256="",
        effective_date=effective_date,
        expiry_date=expiry_date,
        processing_status="UPLOADED",
        lifecycle_status=lifecycle_status,
    )
    db.add(version)
    db.flush()

    dest_dir = _user_upload_dir(user_id, kb.id, doc.id, version.id)
    dest = dest_dir / file_name
    shutil.copy2(str(src), str(dest))
    version.file_path = str(dest)
    version.sha256 = _sha256_of(dest)

    # point the logical document at this version as current
    doc.current_version_id = version.id
    if lifecycle_status == "CURRENT":
        others = (
            db.query(DocumentVersion)
            .filter(
                DocumentVersion.document_id == doc.id,
                DocumentVersion.id != version.id,
            )
            .all()
        )
        for o in others:
            o.lifecycle_status = "HISTORICAL"

    db.commit()
    db.refresh(version)
    return version


def run_document_pipeline(db: Session, version_id: int) -> None:
    """Execute PARSING -> CHUNKING -> INDEXING -> READY for a version."""
    version = db.get(DocumentVersion, version_id)
    if version is None:
        return
    doc = db.get(Document, version.document_id)
    kb_id = doc.knowledge_base_id if doc else None
    if doc is None or kb_id is None:
        return

    def set_status(status: str, error: str | None = None) -> None:
        version.processing_status = status
        version.error_message = error
        db.commit()

    try:
        # ---- PARSING ----
        set_status("PARSING")
        parser: DocumentParser = get_parser(version.file_type)
        normalized = parser.parse(version.file_path)

        # ---- CHUNKING ----
        set_status("CHUNKING")
        parents = build_parent_child_chunks(
            normalized,
            child_tokens=DEFAULT_CHILD_TOKENS,
            parent_tokens=DEFAULT_PARENT_TOKENS,
            child_overlap=DEFAULT_CHILD_OVERLAP,
        )

        # wipe old chunks (reindex case)
        db.query(Chunk).filter(Chunk.document_version_id == version.id).delete()
        db.flush()

        char_offset = 0
        for parent in parents:
            parent_chunk = Chunk(
                document_version_id=version.id,
                knowledge_base_id=kb_id,
                parent_id=None,
                chunk_type="PARENT",
                content=parent.content,
                heading=parent.heading,
                heading_path=" > ".join(parent.heading_path) if parent.heading_path else parent.heading,
                page_number=parent.page_number,
                chunk_index=0,
                token_count=estimate_tokens(parent.content),
                char_start=char_offset,
                char_end=char_offset + len(parent.content),
                meta={},
            )
            db.add(parent_chunk)
            db.flush()
            for child_index, child in enumerate(parent.children):
                child_chunk = Chunk(
                    document_version_id=version.id,
                    knowledge_base_id=kb_id,
                    parent_id=parent_chunk.id,
                    chunk_type="CHILD",
                    content=child.content,
                    heading=child.heading,
                    heading_path=" > ".join(child.heading_path) if child.heading_path else child.heading,
                    page_number=child.page_number,
                    chunk_index=child_index,
                    token_count=estimate_tokens(child.content),
                    char_start=char_offset,
                    char_end=char_offset + len(child.content),
                    meta={"section": child.heading},
                )
                db.add(child_chunk)
            char_offset += len(parent.content)
        db.flush()

        # ---- INDEXING ----
        set_status("INDEXING")
        from app.services.embedding_index_service import index_document_version

        indexed = index_document_version(db, version)
        if not indexed:
            # Embedding unavailable: chunks exist, dense can't serve this yet.
            set_status(
                "NEEDS_REINDEX",
                "Embedding 模型未就绪，向量索引未完成；关键词检索仍可使用。",
            )
            bm25_cache.invalidate([kb_id])
            return

        set_status("READY")
        bm25_cache.invalidate([kb_id])
    except ScanPdfError as exc:
        set_status("FAILED", str(exc))
        # remove chunks from partially processed scans — do not create empty index
        db.query(Chunk).filter(Chunk.document_version_id == version.id).delete()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        version = db.get(DocumentVersion, version_id)
        if version is not None:
            set_status("FAILED", f"处理失败: {exc}")


def get_document_versions(db: Session, document_id: int) -> list[DocumentVersion]:
    return (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.created_at.desc())
        .all()
    )


def chunk_preview(db: Session, version_id: int, limit: int = 5) -> dict[str, Any]:
    total = (
        db.query(Chunk)
        .filter(Chunk.document_version_id == version_id, Chunk.chunk_type == "CHILD")
        .count()
    )
    rows = (
        db.query(Chunk)
        .filter(Chunk.document_version_id == version_id, Chunk.chunk_type == "CHILD")
        .order_by(Chunk.id.asc())
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "items": [
            {
                "chunk_index": c.chunk_index,
                "heading_path": c.heading_path,
                "page_number": c.page_number,
                "content": c.content[:300],
                "token_count": c.token_count,
            }
            for c in rows
        ],
    }
