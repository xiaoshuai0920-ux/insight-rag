"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("insightrag")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Bootstrap: create tables + pgvector extension; warn about provider readiness.
    from app.db.session import Base, engine
    import app.models  # noqa: F401  (ensure all models are registered on Base)

    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        Base.metadata.create_all(bind=conn)
    logger.info("Database schema ensured")

    from app.providers.llm.base import ollama_available

    if ollama_available():
        logger.info("Ollama detected at %s", settings.OLLAMA_BASE_URL)
    else:
        logger.warning("Ollama not reachable — LLM features will show '本地模型不可用'")
    yield


app = FastAPI(
    title="InsightRAG API",
    description="企业级多知识库智能检索与问答平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip()
        for o in settings.CORS_ORIGINS.split(",")
        if o.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
from app.api.auth import router as auth_router  # noqa: E402
from app.api.chat import router as chat_router  # noqa: E402
from app.api.conversations import router as conversations_router  # noqa: E402
from app.api.documents import router as documents_router  # noqa: E402
from app.api.evaluation import router as evaluation_router  # noqa: E402
from app.api.knowledge_bases import router as kb_router  # noqa: E402
from app.api.misc import router as misc_router  # noqa: E402
from app.api.retrieval import router as retrieval_router  # noqa: E402
from app.api.settings import router as settings_router  # noqa: E402

app.include_router(auth_router)
app.include_router(kb_router)
app.include_router(documents_router)
app.include_router(conversations_router)
app.include_router(chat_router)
app.include_router(retrieval_router)
app.include_router(evaluation_router)
app.include_router(settings_router)
app.include_router(misc_router)


@app.get("/")
def root():
    return {"app": "InsightRAG", "docs": "/docs", "status": "ok"}
