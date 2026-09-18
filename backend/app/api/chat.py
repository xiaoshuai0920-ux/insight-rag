"""Chat SSE API."""
from __future__ import annotations

import asyncio
import queue
import threading

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import SessionLocal, get_db
from app.models import User
from app.services.chat_service import stream_chat_answer

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatStreamRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: int | None = None
    kb_ids: list[int] | None = None


@router.post("/stream")
def chat_stream(
    payload: ChatStreamRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id

    def event_generator():
        q: queue.Queue = queue.Queue()
        sentinel = object()

        def worker() -> None:
            local_db = SessionLocal()
            try:
                for chunk in stream_chat_answer(
                    local_db, user_id, payload.conversation_id, payload.message, payload.kb_ids
                ):
                    q.put(chunk)
            except Exception as exc:  # noqa: BLE001
                import json

                q.put(
                    f"event: error\ndata: {json.dumps({'message': f'服务器内部错误: {exc}'}, ensure_ascii=False)}\n\n"
                )
            finally:
                local_db.close()
                q.put(sentinel)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        while True:
            item = q.get()
            if item is sentinel:
                break
            yield item

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
