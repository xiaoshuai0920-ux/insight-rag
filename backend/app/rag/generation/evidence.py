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

# 分类修饰词：出现时表示"并列分类"（不同城市/级别/角色/方式），而非数值冲突。
_CLASSIFIERS = [
    "一线城市", "二线城市", "三线城市", "四线城市", "新一线城市",
    "北京", "上海", "广州", "深圳", "成都", "杭州", "重庆", "西安",
    "天津", "南京", "武汉", "长沙", "郑州", "青岛", "大连", "苏州", "厦门",
    "直属主管", "部门负责人", "财务总监", "总经理", "副总经理",
    "采购总监", "客服主管", "产品经理",
    "高铁", "动车", "飞机", "经济舱", "商务舱", "一等座", "二等座",
]


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
    """Detect obvious numeric conflicts among sources.

    A conflict requires two sources to state the SAME fact with DIFFERENT
    values. Naive unit-grouping over-flags parallel categories (一线 500 vs
    二线 350) and unrelated subjects (招待 1000 vs 报销 500). So each match is
    reduced to:

      - classifier: the category word nearest the number (二线城市 / 部门负责人…)
      - norm: the surrounding phrase with numbers + classifiers + punctuation
        stripped

    Two different values conflict only when classifier AND norm both match.
    """
    records: list[tuple[str, float, str, str | None, str]] = []
    for h in hits:
        text = (h.parent_content or h.content or "")[:1500]
        title = h.document_title
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(元|美元|%|天|个月|小时)", text):
            value = float(m.group(1))
            unit = m.group(2)
            start = max(0, m.start() - 20)
            context = text[start : m.start()]
            found = [c for c in _CLASSIFIERS if c in context]
            classifier = max(found, key=context.rfind) if found else None
            norm = re.sub(r"\d+(?:\.\d+)?", "", context)
            for c in _CLASSIFIERS:
                norm = norm.replace(c, "")
            norm = re.sub(r"[\s，。、;；:：()（）%\-/\.]+", "", norm)
            records.append((unit, value, title, classifier, norm))

    by_unit: dict[str, list[tuple[float, str, str | None, str]]] = {}
    for unit, value, title, classifier, norm in records:
        by_unit.setdefault(unit, []).append((value, title, classifier, norm))

    conflicts: list[dict[str, Any]] = []
    for unit, recs in by_unit.items():
        distinct_values = sorted({r[0] for r in recs})
        if len(distinct_values) <= 1:
            continue
        conflict_found = False
        for i in range(len(recs)):
            for j in range(i + 1, len(recs)):
                v1, _t1, c1, n1 = recs[i]
                v2, _t2, c2, n2 = recs[j]
                if v1 == v2:
                    continue
                if c1 == c2 and n1 and n1 == n2:
                    conflict_found = True
                    break
            if conflict_found:
                break
        if conflict_found:
            descriptions = []
            for v in distinct_values:
                sources = sorted({r[1] for r in recs if r[0] == v})
                descriptions.append({"value": f"{v:g}{unit}", "sources": sources})
            conflicts.append({"unit": unit, "values": descriptions})
    return conflicts[:3]
