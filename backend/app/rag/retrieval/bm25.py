"""BM25 retrieval over CHILD chunks with jieba Chinese tokenization.

Maintains an in-memory index cache per knowledge-base scope. Cache is
invalidated when chunks change (upload/delete/reindex).

Uses BM25Plus (delta=1.0) instead of BM25Okapi: on very small corpora the
Okapi variant can produce negative IDF values, which would make every match
score non-positive and get filtered. BM25Plus keeps IDF strictly positive so
lexical recall is reliable at demo scale.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

import jieba
from rank_bm25 import BM25Plus
from sqlalchemy.orm import Session

from app.models import Chunk

jieba.initialize()

_STOPWORDS = set(
    "的 了 和 是 就 都 而 及 与 著 或 一个 没有 我们 你们 他们 它 在 上 下 中 里 也 很 到 说 要 去 会 着 没 看 好 自己 这 那 你 我 他 她 吗 呢 吧 啊 把 等 还 并 但 ".split()
)

# Punctuation / symbol tokens never help lexical matching.
_PUNCT = set("，。、；：？！“”‘’（）《》〈〉【】…—·,.!?;:\"'()[]{}<>/\\|-_+=*&^%$#@~` \t\n\r")

# Synonym map to improve lexical recall for common policy wording variants.
_SYNONYMS: dict[str, list[str]] = {
    "报销": ["报销", "核销"],
    "出差": ["出差", "差旅"],
    "住宿": ["住宿", "酒店", "旅馆"],
    "补贴": ["补贴", "补助", "津贴"],
    "请假": ["请假", "休假"],
    "年假": ["年假", "年休假", "带薪年假"],
    "离职": ["离职", "辞退", "解除劳动合同"],
    "入职": ["入职", "报到", "新员工"],
    "发票": ["发票", "票据"],
    "退款": ["退款", "退费"],
    "工牌": ["工牌", "工卡", "门禁卡"],
    "设备": ["设备", "电脑", "办公设备"],
}


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for tok in jieba.lcut(text or ""):
        tok = tok.strip()
        if not tok or tok in _STOPWORDS or tok in _PUNCT:
            continue
        tokens.append(tok)
    return tokens


def expand_query_tokens(query: str) -> list[str]:
    base = tokenize(query)
    expanded: list[str] = list(base)
    lowered = query
    for key, syns in _SYNONYMS.items():
        if key in lowered or any(s in base for s in syns):
            for s in syns:
                for t in tokenize(s):
                    if t not in expanded:
                        expanded.append(t)
    return expanded


@dataclass
class Bm25Hit:
    chunk_id: int
    score: float
    hit_keywords: list[str] = field(default_factory=list)


@dataclass
class _IndexEntry:
    bm25: BM25Plus | None
    chunk_ids: list[int]
    tokenized_docs: list[list[str]]
    chunk_meta: dict[int, Chunk]
    built_at: float


class Bm25IndexCache:
    """Thread-safe in-process BM25 index cache."""

    def __init__(self) -> None:
        self._cache: dict[str, _IndexEntry] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(kb_ids: tuple[int, ...]) -> str:
        return ",".join(str(i) for i in sorted(kb_ids))

    def invalidate(self, kb_ids: list[int] | None = None) -> None:
        with self._lock:
            # scope keys are combos; simplest correct approach: full clear
            self._cache.clear()

    def get_index(self, db: Session, kb_ids: list[int]) -> _IndexEntry:
        key = self._key(tuple(kb_ids))
        with self._lock:
            entry = self._cache.get(key)
        if entry is not None:
            return entry
        entry = self._build(db, kb_ids)
        with self._lock:
            self._cache[key] = entry
        return entry

    def _build(self, db: Session, kb_ids: list[int]) -> _IndexEntry:
        rows = (
            db.query(Chunk)
            .filter(
                Chunk.knowledge_base_id.in_(kb_ids),
                Chunk.chunk_type == "CHILD",
            )
            .all()
        )
        tokenized_docs: list[list[str]] = []
        chunk_ids: list[int] = []
        chunk_meta: dict[int, Chunk] = {}
        for chunk in rows:
            tokens = tokenize(chunk.content)
            tokenized_docs.append(tokens)
            chunk_ids.append(chunk.id)
            chunk_meta[chunk.id] = chunk
        bm25 = BM25Plus(tokenized_docs, delta=1.0) if tokenized_docs else None
        return _IndexEntry(
            bm25=bm25,
            chunk_ids=chunk_ids,
            tokenized_docs=tokenized_docs,
            chunk_meta=chunk_meta,
            built_at=time.time(),
        )


bm25_cache = Bm25IndexCache()


def bm25_search(
    db: Session, kb_ids: list[int], query: str, top_k: int = 10
) -> list[Bm25Hit]:
    entry = bm25_cache.get_index(db, kb_ids)
    if entry.bm25 is None or not entry.chunk_ids:
        return []
    query_tokens = expand_query_tokens(query)
    if not query_tokens:
        query_tokens = tokenize(query) or [query]
    scores = entry.bm25.get_scores(query_tokens)
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[: top_k * 2]
    hits: list[Bm25Hit] = []
    for i in order:
        score = float(scores[i])
        if score <= 0:
            continue
        chunk_id = entry.chunk_ids[i]
        doc_tokens = entry.tokenized_docs[i]
        hit_kw = [t for t in query_tokens if t in doc_tokens][:6]
        hits.append(Bm25Hit(chunk_id=chunk_id, score=score, hit_keywords=hit_kw))
        if len(hits) >= top_k:
            break
    return hits
