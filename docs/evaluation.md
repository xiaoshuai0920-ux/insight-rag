# InsightRAG 检索评测结果

> 生成时间：2026-09-18 03:42 UTC
> 评测用例：41 条（demo ground truth，见 `demo-data/golden-dataset.json`）
> 评测用户：demo@nexatech.demo

本文件结果全部来自真实检索运行，未伪造任何指标。

## 指标说明

- **Recall@5**：期望文档出现在检索结果前 5 名的比例
- **MRR**：期望文档首次命中位置的倒数平均值
- **Avg Latency**：单条查询的平均检索耗时（毫秒）

## 结果汇总

| 策略 | Recall@5 | MRR | Avg Latency (ms) | 状态 |
|------|----------|-----|------------------|------|
| dense | 0.805 | 0.480 | 2136.3 | DONE |
| hybrid | 1.000 | 0.760 | 2132.0 | DONE |
| hybrid_rerank | 1.000 | 0.963 | 2806.6 | DONE |

## 说明

- 若某策略状态为 `FAILED`，通常意味着对应依赖（Embedding / Reranker）未就绪。
- 评测在 demo 规模（万级 Chunk 内）使用 exact cosine similarity，不涉及 HNSW/IVFFlat。
- RRF constant、Reranker top_k 等为工程默认参数，不宣称全局最优。
