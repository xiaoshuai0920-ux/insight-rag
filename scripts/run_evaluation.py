"""Run the Golden Dataset evaluation from the command line.

Computes Recall@5 / MRR / average retrieval latency for dense / hybrid /
hybrid_rerank strategies using real retrieval runs, and writes a Markdown
report to docs/evaluation.md.

Usage:
    python scripts/run_evaluation.py                # all strategies
    python scripts/run_evaluation.py --strategy hybrid
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.rag.evaluation.runner import evaluate_strategy, load_golden_dataset  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = PROJECT_ROOT / "docs" / "evaluation.md"

STRATEGIES = ["dense", "hybrid", "hybrid_rerank"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run InsightRAG evaluation")
    parser.add_argument("--strategy", choices=STRATEGIES, help="single strategy only")
    args = parser.parse_args()

    cases = load_golden_dataset()
    if not cases:
        print("未找到 golden-dataset.json，无法评测")
        sys.exit(1)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "demo@nexatech.demo").first()
        if user is None:
            user = db.query(User).order_by(User.id.asc()).first()
        if user is None:
            print("数据库中没有用户，请先运行 seed_demo_data.py")
            sys.exit(1)

        strategies = [args.strategy] if args.strategy else STRATEGIES
        results = []
        for strategy in strategies:
            print(f"[eval] 运行策略: {strategy} ...")
            run, _items = evaluate_strategy(db, user.id, strategy, cases)
            results.append(run)
            print(
                f"[eval]   Recall@5={run.recall_at_5} MRR={run.mrr} "
                f"avg_latency_ms={run.avg_latency_ms} status={run.status}"
            )

        _write_report(results, cases, user)
        print(f"[eval] 报告已写入 {REPORT_PATH}")
    finally:
        db.close()


def _write_report(results, cases, user) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# InsightRAG 检索评测结果",
        "",
        f"> 生成时间：{now}",
        f"> 评测用例：{len(cases)} 条（demo ground truth，见 `demo-data/golden-dataset.json`）",
        f"> 评测用户：{user.email}",
        "",
        "本文件结果全部来自真实检索运行，未伪造任何指标。",
        "",
        "## 指标说明",
        "",
        "- **Recall@5**：期望文档出现在检索结果前 5 名的比例",
        "- **MRR**：期望文档首次命中位置的倒数平均值",
        "- **Avg Latency**：单条查询的平均检索耗时（毫秒）",
        "",
        "## 结果汇总",
        "",
        "| 策略 | Recall@5 | MRR | Avg Latency (ms) | 状态 |",
        "|------|----------|-----|------------------|------|",
    ]
    for r in results:
        recall = f"{r.recall_at_5:.3f}" if r.recall_at_5 is not None else "N/A"
        mrr = f"{r.mrr:.3f}" if r.mrr is not None else "N/A"
        latency = f"{r.avg_latency_ms:.1f}" if r.avg_latency_ms is not None else "N/A"
        lines.append(f"| {r.strategy} | {recall} | {mrr} | {latency} | {r.status} |")

    lines += [
        "",
        "## 说明",
        "",
        "- 若某策略状态为 `FAILED`，通常意味着对应依赖（Embedding / Reranker）未就绪。",
        "- 评测在 demo 规模（万级 Chunk 内）使用 exact cosine similarity，不涉及 HNSW/IVFFlat。",
        "- RRF constant、Reranker top_k 等为工程默认参数，不宣称全局最优。",
        "",
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
