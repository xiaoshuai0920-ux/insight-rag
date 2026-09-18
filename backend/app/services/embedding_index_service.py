"""Embedding index service: generate embeddings for CHILD chunks."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import Chunk, DocumentVersion
from app.providers.embedding.base import EmbeddingError, EmbeddingNotReady, get_embedding_provider

logger = logging.getLogger(__name__)


def index_document_version(
    db: Session, version: DocumentVersion, profile=None, batch_size: int = 32
) -> bool:
    """Embed all CHILD chunks of a version under the ACTIVE profile (or given).

    Returns True when embeddings were written, False when the embedding
    provider is not ready (caller decides the resulting status).
    """
    from app.models import ChunkEmbedding
    from app.services.settings_service import get_active_embedding_profile

    if profile is None:
        profile = get_active_embedding_profile(db)
    if profile is None:
        # Try to bootstrap the default profile once.
        profile = ensure_default_profile(db)
    if profile is None:
        return False

    children = (
        db.query(Chunk)
        .filter(Chunk.document_version_id == version.id, Chunk.chunk_type == "CHILD")
        .order_by(Chunk.id.asc())
        .all()
    )
    if not children:
        return False

    provider = get_embedding_provider(model=profile.model_name if profile.provider != "ollama" else None)

    # remove existing embeddings for this version under this profile
    child_ids = [c.id for c in children]
    db.query(ChunkEmbedding).filter(
        ChunkEmbedding.chunk_id.in_(child_ids),
        ChunkEmbedding.embedding_profile_id == profile.id,
    ).delete(synchronize_session=False)

    try:
        for i in range(0, len(children), batch_size):
            batch = children[i : i + batch_size]
            vectors = provider.embed_documents([c.content for c in batch])
            for chunk, vec in zip(batch, vectors):
                db.add(
                    ChunkEmbedding(
                        chunk_id=chunk.id,
                        embedding_profile_id=profile.id,
                        embedding=vec,
                    )
                )
            db.flush()
        db.commit()
        return True
    except (EmbeddingError, EmbeddingNotReady) as exc:
        db.rollback()
        logger.warning("Embedding indexing failed: %s", exc)
        return False
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.warning("Embedding indexing unexpected error: %s", exc)
        return False


def ensure_default_profile(db: Session):
    """Create + activate the default embedding profile when provider is ready."""
    from app.models import EmbeddingProfile
    from app.services.settings_service import get_setting, set_setting

    provider_name = get_setting(db, "embedding_provider", "ollama")
    provider = get_embedding_provider()
    try:
        dim = provider.get_dimension()
    except Exception:
        dim = None
    if dim is None:
        return None
    existing = (
        db.query(EmbeddingProfile)
        .filter(
            EmbeddingProfile.provider == provider_name,
            EmbeddingProfile.status == "ACTIVE",
        )
        .first()
    )
    if existing is not None:
        set_setting(db, "active_embedding_profile_id", existing.id)
        db.commit()
        return existing
    profile = EmbeddingProfile(
        provider=provider_name,
        model_name=getattr(provider, "model", "") or "",
        dimension=dim,
        status="ACTIVE",
    )
    from datetime import datetime, timezone

    profile.activated_at = datetime.now(timezone.utc)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    set_setting(db, "active_embedding_profile_id", profile.id)
    db.commit()
    return profile
