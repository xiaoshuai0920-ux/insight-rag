"""Chat service: retrieval -> evidence -> LLM SSE streaming -> citations."""
from __future__ import annotations

import json
import queue
import threading
from dataclasses import dataclass
from typing import Any, Generator

from sqlalchemy.orm import Session

from app.models import Conversation, Document, DocumentVersion, Message, MessageCitation
from app.providers.embedding.base import EmbeddingError
from app.providers.llm.base import LLMError, LLMNotConfigured, get_llm_provider
from app.rag.generation.evidence import EvidenceState, assess_evidence
from app.rag.generation.prompts import (
    INSUFFICIENT_ANSWER,
    SYSTEM_PROMPT,
    build_user_prompt,
    detect_policy_footer,
)
from app.rag.retrieval.pipeline import RetrievalParams, run_retrieval
from app.services.settings_service import get_active_embedding_profile


def sse_event(event: str, data: dict | str) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


@dataclass
class ChatContext:
    conversation_id: int
    user_message_id: int
    kb_ids: list[int] | None
    scope_note: str = ""


def create_conversation(db: Session, user_id: int, title: str = "新的对话") -> Conversation:
    conv = Conversation(user_id=user_id, title=title[:200])
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def stream_chat_answer(
    db: Session,
    user_id: int,
    conversation_id: int | None,
    question: str,
    kb_ids: list[int] | None,
) -> Generator[str, None, None]:
    """Full SSE chat flow. Yields SSE-formatted strings.

    Events: status / evidence / answer / citations / meta / done / error
    """
    from app.db.session import SessionLocal
    from app.rag.retrieval.pipeline import validate_kb_scope

    # 0. Resolve / create conversation
    if conversation_id:
        conv = db.get(Conversation, conversation_id)
        if conv is None or conv.user_id != user_id:
            yield sse_event("error", {"message": "对话不存在或无权访问"})
            return
    else:
        conv = create_conversation(db, user_id, title=question[:60] or "新的对话")

    conv_id = conv.id
    yield sse_event("meta", {"conversation_id": conv_id, "title": conv.title})

    # 1. Persist user message with KB scope snapshot
    scope_ids: list[int] = []
    scope_note = "全部知识库"
    try:
        scope_ids = validate_kb_scope(db, user_id, kb_ids)
    except ValueError as exc:
        yield sse_event("error", {"message": str(exc)})
        return
    if kb_ids:
        scope_note = "所选知识库"

    user_msg = Message(
        conversation_id=conv_id,
        role="USER",
        content=question,
        retrieval_meta={"kb_scope": scope_ids, "scope_note": scope_note},
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    # 2. Status: retrieving
    yield sse_event("status", {"stage": "retrieving", "message": "正在检索知识…"})

    retrieval = None
    try:
        retrieval = run_retrieval(
            db, user_id, kb_ids, question, RetrievalParams(), scope_note=scope_note
        )
    except Exception as exc:  # noqa: BLE001
        yield sse_event("error", {"message": f"检索过程出错: {exc}"})
        return

    # embedding not ready -> dense unavailable, report honestly
    active_profile = get_active_embedding_profile(db)
    if active_profile is None and retrieval.strategy in ("hybrid", "dense", "hybrid_rerank"):
        yield sse_event(
            "status",
            {"stage": "notice", "message": "Embedding 索引未就绪，本次仅使用关键词检索（BM25）"},
        )

    # 3. Evidence assessment
    yield sse_event("status", {"stage": "organizing", "message": "正在组织证据…"})
    evidence: EvidenceState = assess_evidence(retrieval.hits)

    retrieval_meta: dict[str, Any] = {
        "kb_scope": scope_ids,
        "scope_note": scope_note,
        "strategy": retrieval.strategy,
        "stages": [s.to_dict() for s in retrieval.stages],
        "total_latency_ms": round(retrieval.total_latency_ms, 1),
        "reranker_used": retrieval.reranker_used,
        "hit_count": len(retrieval.hits),
    }

    # 4. Generate answer
    answer_chunks: list[str] = []
    error_message: str | None = None

    if evidence.status == "INSUFFICIENT":
        answer_chunks = [INSUFFICIENT_ANSWER]
    else:
        yield sse_event("status", {"stage": "generating", "message": "正在生成回答…"})
        prompt = build_user_prompt(question, retrieval.hits)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        try:
            provider = get_llm_provider()
            for piece in provider.stream_chat(messages):
                answer_chunks.append(piece)
                yield sse_event("answer", {"delta": piece})
        except LLMNotConfigured as exc:
            error_message = str(exc)
        except LLMError as exc:
            error_message = str(exc)
        except Exception as exc:  # noqa: BLE001
            error_message = f"生成回答失败: {exc}"

    full_answer = "".join(answer_chunks)

    if error_message:
        retrieval_meta["llm_error"] = error_message
        fallback = (
            "（回答生成失败）\n\n"
            f"原因：{error_message}\n\n"
            "检索已完成，下方引用来源仍然有效。请检查模型配置后重试。"
        )
        full_answer = full_answer or fallback
        if not answer_chunks:
            yield sse_event("answer", {"delta": full_answer})

    footer = detect_policy_footer(retrieval.hits)
    if footer and evidence.status != "INSUFFICIENT":
        full_answer_with_footer = full_answer + f"\n\n---\n{footer}"
    else:
        full_answer_with_footer = full_answer

    # 5. Persist assistant message + citations
    assistant_msg = Message(
        conversation_id=conv_id,
        role="ASSISTANT",
        content=full_answer_with_footer,
        evidence_status=evidence.status,
        retrieval_meta=retrieval_meta,
    )
    db.add(assistant_msg)
    db.flush()

    citations_payload: list[dict[str, Any]] = []
    for idx, hit in enumerate(retrieval.hits, start=1):
        dv = db.get(DocumentVersion, hit.document_version_id)
        citation = MessageCitation(
            message_id=assistant_msg.id,
            citation_index=idx,
            document_id=hit.document_id,
            document_version_id=hit.document_version_id,
            chunk_id=hit.chunk_id,
            quote_text=hit.parent_content or hit.content,
            page_number=hit.page_number,
            heading_path=hit.heading_path or hit.heading,
            effective_date=dv.effective_date if dv else None,
        )
        db.add(citation)
        payload = hit.to_citation_dict()
        payload["citation_index"] = idx
        citations_payload.append(payload)

    # keep title fresh
    if conv.title in ("新的对话", "") and question:
        conv.title = question[:60]
    db.commit()

    yield sse_event("evidence", {**evidence.to_dict(), "hit_count": len(retrieval.hits)})
    yield sse_event(
        "citations",
        {"citations": citations_payload, "retrieval_meta": retrieval_meta},
    )
    yield sse_event("done", {"message_id": assistant_msg.id, "conversation_id": conv_id})


def get_conversation_messages(db: Session, user_id: int, conversation_id: int) -> dict[str, Any]:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user_id:
        raise ValueError("对话不存在或无权访问")
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    out: list[dict[str, Any]] = []
    for m in messages:
        item: dict[str, Any] = {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "evidence_status": m.evidence_status,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        if m.role == "ASSISTANT":
            item["citations"] = [
                {
                    "citation_index": c.citation_index,
                    "document_id": c.document_id,
                    "document_version_id": c.document_version_id,
                    "chunk_id": c.chunk_id,
                    "quote_text": c.quote_text,
                    "page_number": c.page_number,
                    "heading_path": c.heading_path,
                    "effective_date": c.effective_date.isoformat() if c.effective_date else None,
                    "document_title": (db.get(Document, c.document_id).title if c.document_id else ""),
                    "version_label": (
                        db.get(DocumentVersion, c.document_version_id).version_label
                        if c.document_version_id
                        else ""
                    ),
                }
                for c in m.citations
            ]
            item["retrieval_meta"] = m.retrieval_meta
        elif m.role == "USER":
            item["retrieval_meta"] = m.retrieval_meta
        out.append(item)
    return {"id": conv.id, "title": conv.title, "messages": out}
