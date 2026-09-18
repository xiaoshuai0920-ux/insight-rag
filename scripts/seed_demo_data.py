"""Seed NexaTech demo data into the database.

Creates a demo user, 6 knowledge bases, ~24 logical documents (with the travel
policy having V2.0/HISTORICAL and V3.0/CURRENT versions), then runs the full
document pipeline for each version.

Usage:
    python scripts/seed_demo_data.py            # seed (idempotent by title)
    python scripts/seed_demo_data.py --reset    # wipe demo user's data first

Front matter of each demo Markdown file carries title / knowledge_base /
department / category / version / file_version / effective_date /
lifecycle_status. This script parses that metadata directly (the parser itself
strips it from the body).
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Chunk,
    Document,
    DocumentVersion,
    KnowledgeBase,
    User,
)
from app.core.security import hash_password  # noqa: E402
from app.services.document_service import (  # noqa: E402
    create_document_with_version,
    run_document_pipeline,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "demo-data" / "documents"

DEMO_USER = {
    "username": "demo",
    "email": "demo@nexatech.demo",
    "password": "NexaTech2026",
}

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_front_matter(text: str) -> dict[str, str]:
    m = _FM_RE.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip("\"'")
    return out


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _get_or_create_demo_user(db) -> User:
    user = db.query(User).filter(User.email == DEMO_USER["email"]).first()
    if user is None:
        user = User(
            username=DEMO_USER["username"],
            email=DEMO_USER["email"],
            password_hash=hash_password(DEMO_USER["password"]),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"[seed] 创建演示账号: {DEMO_USER['email']}")
    return user


def _reset_user(db, user: User) -> None:
    from sqlalchemy import delete

    kb_ids = [kb.id for kb in db.query(KnowledgeBase).filter(KnowledgeBase.user_id == user.id)]
    if not kb_ids:
        return
    for kb_id in kb_ids:
        doc_ids = [d.id for d in db.query(Document).filter(Document.knowledge_base_id == kb_id)]
        for doc_id in doc_ids:
            ver_ids = [
                v.id for v in db.query(DocumentVersion).filter(DocumentVersion.document_id == doc_id)
            ]
            for vid in ver_ids:
                db.execute(delete(Chunk).where(Chunk.document_version_id == vid))
                db.execute(delete(DocumentVersion).where(DocumentVersion.id == vid))
            db.execute(delete(Document).where(Document.id == doc_id))
        db.execute(delete(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    db.commit()
    print("[seed] 已清空演示用户既有数据")


def seed(reset: bool = False) -> None:
    import json

    manifest = json.loads(
        (PROJECT_ROOT / "demo-data" / "seed_manifest.json").read_text(encoding="utf-8")
    )

    db = SessionLocal()
    try:
        user = _get_or_create_demo_user(db)
        if reset:
            _reset_user(db, user)

        total_docs = 0
        total_versions = 0
        for kb_spec in manifest["knowledge_bases"]:
            kb = db.query(KnowledgeBase).filter(
                KnowledgeBase.user_id == user.id, KnowledgeBase.name == kb_spec["name"]
            ).first()
            if kb is None:
                kb = KnowledgeBase(
                    user_id=user.id,
                    name=kb_spec["name"],
                    description=kb_spec["description"],
                    category=kb_spec["category"],
                )
                db.add(kb)
                db.commit()
                db.refresh(kb)
                print(f"[seed] 创建知识库: {kb.name}")
            else:
                print(f"[seed] 知识库已存在: {kb.name}")

            for doc_spec in kb_spec["documents"]:
                path = DOCS_DIR / doc_spec["file"]
                if not path.exists():
                    print(f"[seed] 跳过缺失文件: {path.name}")
                    continue
                text = path.read_text(encoding="utf-8")
                meta = _parse_front_matter(text)
                title = meta.get("title") or path.stem
                # Use the clean title (from front matter) as the file name so the
                # logical document title matches golden-dataset expected_document.
                clean_file_name = f"{title}.md"
                version = create_document_with_version(
                    db,
                    kb,
                    user.id,
                    clean_file_name,
                    str(path),
                    version_label=meta.get("version", "V1.0"),
                    file_version=meta.get("file_version", "1.0"),
                    effective_date=_parse_date(meta.get("effective_date")),
                    lifecycle_status=meta.get("lifecycle_status", "CURRENT"),
                    department=meta.get("department", ""),
                    category=meta.get("category", ""),
                )
                total_versions += 1
                total_docs += 1
                print(f"[seed]   {title} -> {version.version_label} (file {version.file_version})")
                run_document_pipeline(db, version.id)
                db.refresh(version)
                print(f"[seed]     pipeline status = {version.processing_status}")

        print(f"[seed] 完成: {total_docs} 个逻辑文档 / {total_versions} 个版本")
        print(f"[seed] 演示账号: {DEMO_USER['email']} / {DEMO_USER['password']}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed NexaTech demo data")
    parser.add_argument("--reset", action="store_true", help="wipe demo user data first")
    args = parser.parse_args()
    seed(reset=args.reset)
