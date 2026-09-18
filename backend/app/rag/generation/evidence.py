"""Evidence state assessment.

States: SUFFICIENT / INSUFFICIENT / CONFLICTING
- No hits or top hit below threshold -> INSUFFICIENT
- Multiple current sources conflicting on core numbers/dates -> CONFLICTING
- Otherwise -> SUFFICIENT

Deliberately lightweight and explainable — no fabricated confidence scores.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

MIN_TOP_SIMILARITY = 0.35
MIN_TOP_BM25 = 1.0

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_DATE_RE = re.compile(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}")


@dataclass
class EvidenceState:
    status: str  # SUFFICIENT / INSUFFICIENT / CONFLICTING
    reason: str = ""
    conflicts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "reason": self.reason, "conflicts": self.conflicts}


def assess_evidence(
    hits: list,
    has_scores: bool = True,
    min_similarity: float = MIN_TOP_SIMILARITY,
) -> EvidenceState:
    if not hits:
        return EvidenceState(
            status="INSUFFICIENT",
            reason="当前知识库中未找到足够信息支撑完整回答。",
        )

    if has_scores:
        top = hits[0]
        top_sim = top.dense_similarity
        top_bm25 = top.bm25_score
        has_any_score = (top_sim is not None) or (top_bm25 is not None)
        if has_any_score:
            ok_dense = top_sim is not None and top_sim >= min_similarity
            ok_bm25 = top_bm25 is not None and top_bm25 >= MIN_TOP_BM25
            if not (ok_dense or ok_bm25 or top.reranker_score is not None):
                return EvidenceState(
                    status="INSUFFICIENT",
                    reason="检索到的资料与问题的相关性较低，无法给出有依据的回答。",
                )

    conflicts = _find_value_conflicts(hits)
    if conflicts:
        return EvidenceState(
            status="CONFLICTING",
            reason="不同来源对关键信息（数字/日期）的描述存在不一致，请以下方来源原文为准。",
            conflicts=conflicts,
        )
    return EvidenceState(status="SUFFICIENT", reason="已检索到相关资料")


def _find_value_conflicts(hits: list) -> list[dict[str, Any]]:
    """Detect obvious conflicts among sources on numbers / dates.

    Strategy: collect key numeric+unit facts per source; if two sources give
    different values for the same unit+context keyword, flag as conflicting.
    """
    unit_contexts: dict[str, dict[float, list[str]]] = {}
    for h in hits:
        text = (h.parent_content or h.content or "")[:1200]
        title = h.document_title
        # money values
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(元|美元|%|天|个月|小时)", text):
            value = float(m.group(1))
            unit = m.group(2)
            # context: nearby 30 chars before the match
            start = max(0, m.start() - 30)
            context = text[start : m.end()]
            bucket = unit_contexts.setdefault(unit, {})
            bucket.setdefault(value, [])
            if title not in bucket[value]:
                bucket[value].append(title)

    conflicts: list[dict[str, Any]] = []
    for unit, values in unit_contexts.items():
        if len(values) > 1:
            # only flag when context keywords overlap (same topic)
            descriptions = []
            for value, sources in values.items():
                descriptions.append({"value": f"{value:g}{unit}", "sources": sources})
            conflicts.append({"unit": unit, "values": descriptions})
    return conflicts[:3]
