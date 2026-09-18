"""Prompt builders for grounded generation."""
from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = """你是 InsightRAG 的企业知识问答助手。规则：
1. 只依据提供的资料回答，不要使用资料之外的通用知识补充事实。
2. 回答中使用 [1][2] 样式的引用标记，对应提供的来源编号。
3. 如果资料不足，明确说明“当前知识库中未找到足够信息支撑完整回答”。
4. 如果不同来源信息冲突，指出冲突并分别列出来源。
5. 如果制度要求二次审批或额外流程，必须保留该要求，不得简化为绝对结论。
6. 回答使用简体中文，简洁、结构化（可用列表），避免冗长。"""

INSUFFICIENT_ANSWER = "当前知识库中未找到足够信息支撑完整回答。\n\n建议：\n- 尝试换一种问法或补充关键信息（如城市、部门、时间）。\n- 检查所选知识库范围是否包含相关制度。\n- 确认相关文档是否已上传并完成索引。"


def build_context_block(hits: list, max_chars_per_hit: int = 1600) -> str:
    blocks: list[str] = []
    for i, h in enumerate(hits, start=1):
        meta = []
        if h.heading_path or h.heading:
            meta.append(f"章节: {h.heading_path or h.heading}")
        if h.page_number:
            meta.append(f"页码: {h.page_number}")
        if h.version_label:
            meta.append(f"版本: {h.version_label}")
        if getattr(h, "effective_date", None):
            meta.append(f"生效日期: {h.effective_date}")
        meta_str = "；".join(meta)
        content = (h.parent_content or h.content)[:max_chars_per_hit]
        blocks.append(f"[{i}] 《{h.document_title}》({meta_str})\n{content}")
    return "\n\n".join(blocks)


def build_user_prompt(question: str, hits: list) -> str:
    context = build_context_block(hits)
    return f"""以下是检索到的企业知识库资料：

{context}

---

用户问题：{question}

请依据以上资料回答，并用 [1][2] 标记引用来源。"""


def detect_policy_footer(hits: list) -> str | None:
    """HR / Finance / Compliance knowledge bases get a restrained footer."""
    if not hits:
        return None
    trigger_categories = {"hr", "finance", "compliance", "legal"}
    categories = {getattr(h, "kb_category", "") or "" for h in hits}
    if categories & trigger_categories:
        return "依据当前生效资料生成\n具体执行以制度原文及企业审批流程为准。"
    return None
