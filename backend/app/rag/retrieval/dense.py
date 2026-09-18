"""Dense retrieval over CHILD chunk embeddings (pgvector, exact cosine)."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session


@dataclass
class DenseHit:
    chunk_id: int
    similarity: float


def dense_search(
    db: Session,
    kb_ids: list[int],
    query_embedding: list[float],
    embedding_profile_id: int,
    top_k: int = 10,
) -> list[DenseHit]:
    if not kb_ids or not query_embedding:
        return []
    rows = db.execute(
        sql_text(
            """
            SELECT ce.chunk_id,
                   1 - (ce.embedding <=> :qv) AS similarity
            FROM chunk_embeddings ce
            JOIN chunks c ON c.id = ce.chunk_id
            WHERE ce.embedding_profile_id = :pid
              AND c.knowledge_base_id = ANY(:kb_ids)
              AND c.chunk_type = 'CHILD'
            ORDER BY ce.embedding <=> :qv
            LIMIT :k
            """
        ),
        {
            "qv": str(query_embedding),
            "pid": embedding_profile_id,
            "kb_ids": list(kb_ids),
            "k": top_k,
        },
    ).fetchall()
    return [DenseHit(chunk_id=int(r.chunk_id), similarity=float(r.similarity)) for r in rows]
