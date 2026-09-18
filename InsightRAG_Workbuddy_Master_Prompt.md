# InsightRAG — Workbuddy Master Prompt

> 你现在是该项目的主执行工程师。请在当前工作区从零到一自动完成 InsightRAG，并持续执行到项目可运行、可演示、可测试、可评估、可推送 GitHub 为止。除非遇到会破坏用户已有重要数据的操作，否则不要中途停下来等待确认。

---

## 0. 核心任务

项目名称：**InsightRAG**  
中文副标题：**企业级多知识库智能检索与问答平台**

目标岗位：AI 应用开发实习生 / RAG 应用开发实习生。

项目定位：面向企业内部知识管理场景，支持多知识库、PDF/DOCX/Markdown/TXT 文档解析、结构化切片、Dense Retrieval、BM25、Hybrid Search、RRF、Reranker、Parent-Child Retrieval、Citation 溯源、SSE 流式问答、Retrieval Lab、Golden Dataset 与检索评测。

这是一个本科大四水平的高质量工程项目，不做研究型堆料。所有能力必须能解释、能运行、能验证。

### 总原则

1. 优先保证正确性、可解释性、可运行性，不追求技术名词堆叠。
2. 项目采用模块化单体，不拆微服务。
3. 不使用 Kubernetes、Kafka、RabbitMQ、Celery、Elasticsearch、GraphRAG、复杂 Agent、多模态、OCR、Fine-tuning、LoRA、知识图谱、复杂 RBAC。
4. 不为了“企业级”擅自加入 SSO/MFA/钉钉/飞书/企业微信。首版只做基础 Auth，README 可列为 Future Work。
5. 不伪造性能数据、评测指标、召回率、延迟或“高可信”分数。
6. UI 以随任务提供的 8 张 InsightRAG V2 设计图为唯一视觉基准；可以补齐 Loading / Empty / Error / Modal / Drawer / Toast 等必要状态，但不得擅自重做整体信息架构、配色或主要布局。
7. 若设计图中的示例数字与真实数据库不一致，**真实数据库数据优先**。禁止硬编码截图中的统计数字。
8. 所有 API Key 都通过 `.env` 注入。缺少真实 API Key 时不要暂停开发：保留空配置、提供 `.env.example`，云端能力显示“未配置”，项目其它部分继续完成。
9. `.env`、上传文件、数据库数据、模型缓存、秘密信息绝对不得提交 GitHub。
10. 每完成一个内部阶段必须自己执行测试/启动/接口验证；失败先修复再继续，不要把未验证代码留给用户。

---

# 1. 自动执行方式

内部可以按 Phase 0～8 组织开发，但**不要每个 Phase 完成后停下来问用户**。

执行循环：

```text
分析当前状态
→ 实现当前阶段
→ 自动运行测试/构建/接口验证
→ 若失败：定位 → 修复 → 重测
→ 通过后继续下一阶段
→ 全部阶段完成后做端到端验收
→ 生成真实评测结果（环境允许时）
→ 完善 README / 文档 / Demo 数据
→ Git 初始化、提交、推送 GitHub
→ 输出最终交付说明
```

只有以下情况允许暂停：

- 即将删除或覆盖用户已有的重要、非本项目数据；
- GitHub 最终推送需要用户完成账号授权且当前机器完全未授权。

**模型 API Key 缺失不是暂停理由。**

---

# 2. UI 设计冻结

随本任务提供 8 张 InsightRAG V2 UI 图，请视为 canonical reference：

1. 登录页
2. 工作台 Dashboard
3. 知识库列表
4. 知识库详情 + Document Inspector
5. AI 问答
6. AI 问答 + Source Panel
7. Retrieval Lab
8. 设置页

建议将提供的设计图复制/保存在：

```text
docs/ui-reference/
```

如无法自动复制附件，则不要阻塞开发，至少在 README 中说明 UI 依据已提供设计稿实现。

## 2.1 视觉规范

- Light Enterprise AI SaaS
- 主背景：#F7F8FA 左右的浅灰白
- Surface：#FFFFFF
- Primary：Indigo / #4F46E5 系
- 文字主色：深灰黑
- Border > Shadow，阴影极轻
- Card radius：10～12px
- Input radius：8～10px
- 桌面优先，1440×900 左右设计基准
- Sidebar 约 224px
- Header 约 60px
- 不使用赛博黑、玻璃拟态、大面积霓虹渐变、夸张动画
- 状态不能只靠颜色，必须有文字和/或图标
- Icon-only button 必须有 `aria-label`
- 所有交互有 hover / focus / disabled / loading 状态

## 2.2 响应式边界

- >=1280：完整桌面布局
- 1024～1279：允许收紧间距/折叠部分 sidebar 文案
- 768～1023：右侧 Drawer 改覆盖式
- <768：基础可用即可；Retrieval Lab 不要求完整移动端体验

---

# 3. 技术栈冻结

## Frontend

```text
Vue 3
Vite
TypeScript
Element Plus
Pinia
Vue Router
Axios
Markdown Renderer
SSE 客户端
```

## Backend

```text
Python 3.12+
FastAPI
Pydantic v2
SQLAlchemy 2.x
Alembic
JWT
Passlib / bcrypt 或同级安全密码哈希方案
Pytest
```

## Data

```text
PostgreSQL 16+
pgvector
```

## RAG

```text
Dense Retrieval
BM25
Hybrid Search
RRF
Reranker
Parent-Child Retrieval
Citation
Golden Dataset
Recall@5
MRR
Average Retrieval Latency
```

## Document

```text
PDF（文本型）
DOCX
Markdown
TXT
```

扫描 PDF：检测到无有效文本时明确提示“当前文件可能为扫描件，暂不支持 OCR”，不要生成空索引。

## Deployment

开发阶段：

```text
Frontend：本机
FastAPI：本机
PostgreSQL + pgvector：Docker Compose
Ollama：用户 Windows 主机现有桌面版
```

不要强制将全部服务 Docker 化。

---

# 4. 项目结构

建议结构如下，可在不改变职责边界的前提下微调：

```text
InsightRAG/
├─ backend/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ core/
│  │  ├─ models/
│  │  ├─ schemas/
│  │  ├─ repositories/
│  │  ├─ services/
│  │  ├─ rag/
│  │  │  ├─ parsing/
│  │  │  ├─ chunking/
│  │  │  ├─ embedding/
│  │  │  ├─ retrieval/
│  │  │  ├─ reranking/
│  │  │  ├─ generation/
│  │  │  └─ evaluation/
│  │  ├─ providers/
│  │  │  ├─ llm/
│  │  │  ├─ embedding/
│  │  │  └─ reranker/
│  │  └─ main.py
│  ├─ tests/
│  ├─ alembic/
│  └─ requirements.txt / pyproject.toml
├─ frontend/
│  ├─ src/
│  │  ├─ api/
│  │  ├─ components/
│  │  ├─ layouts/
│  │  ├─ pages/
│  │  ├─ stores/
│  │  ├─ router/
│  │  ├─ composables/
│  │  ├─ utils/
│  │  └─ types/
│  └─ package.json
├─ demo-data/
│  ├─ documents/
│  ├─ golden-dataset.json
│  └─ seed_manifest.json
├─ docs/
│  ├─ ui-reference/
│  ├─ architecture.md
│  ├─ rag-pipeline.md
│  ├─ document-pipeline.md
│  └─ evaluation.md
├─ scripts/
│  ├─ seed_demo_data.py
│  ├─ run_evaluation.py
│  ├─ start_dev.ps1
│  └─ publish_github.ps1
├─ docker-compose.yml
├─ .env.example
├─ .gitignore
├─ README.md
└─ LICENSE
```

业务代码和 RAG 代码必须分开。

---

# 5. 环境变量与 Secrets

创建 `.env.example`，真实 `.env` 不提交。

建议至少支持：

```env
APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=8000
FRONTEND_URL=http://localhost:5173

DATABASE_URL=postgresql+psycopg://insightrag:insightrag@localhost:5432/insightrag
JWT_SECRET=PLEASE_CHANGE_ME
JWT_EXPIRE_MINUTES=1440

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=qwen2.5:7b

OPENAI_COMPATIBLE_BASE_URL=
OPENAI_COMPATIBLE_API_KEY=
OPENAI_COMPATIBLE_LLM_MODEL=

EMBEDDING_PROVIDER=ollama
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OPENAI_COMPATIBLE_EMBEDDING_MODEL=

RERANKER_PROVIDER=local
RERANKER_MODEL=BAAI/bge-reranker-base
```

注意：以上模型名称作为合理默认值/示例，运行时应检测实际可用模型并允许 UI 配置。

如果用户本地已有 Ollama `qwen2.5:7b`，优先自动检测 `/api/tags` 并使用。

如果 `nomic-embed-text` 未安装：

- 可以尝试自动执行 `ollama pull nomic-embed-text`；
- 若网络失败，不要中断整个项目；设置页显示“Embedding 模型未就绪”，并提供明确指引；
- 不得伪造已完成索引和评测。

云端 API Key 为空时：

- 应用可以正常启动；
- OpenAI Compatible Provider 显示“未配置 API Key”；
- 不要崩溃；
- 不要暂停 Workbuddy 执行。

---

# 6. 数据模型与统计口径

必须解决“统计口径、版本、引用来源不一致”问题。

## 6.1 users

```text
id
username
email
password_hash
created_at
updated_at
```

## 6.2 knowledge_bases

```text
id
user_id
name
description
category
created_at
updated_at
```

## 6.3 documents（逻辑文档）

```text
id
knowledge_base_id
title
category
department
tags JSONB
current_version_id nullable
created_at
updated_at
```

一个制度可有多个版本，但仍是同一个 logical document。

## 6.4 document_versions

```text
id
document_id
version_label          # 例如 V3.0
file_version           # 例如 1.2
file_name
file_path
file_type
file_size
sha256
effective_date nullable
expiry_date nullable
processing_status      # UPLOADED/PARSING/CHUNKING/INDEXING/READY/FAILED/NEEDS_REINDEX
lifecycle_status       # CURRENT/HISTORICAL/DRAFT
error_message nullable
created_at
updated_at
```

默认 AI Chat 只搜索 CURRENT + READY + 生效范围合法的版本。

## 6.5 chunks

```text
id
document_version_id
knowledge_base_id
parent_id nullable
chunk_type             # PARENT / CHILD
content
heading
heading_path
page_number nullable
chunk_index
token_count
char_start nullable
char_end nullable
metadata JSONB
created_at
```

仅 CHILD 用于 Dense / BM25 检索；命中后通过 parent_id 回溯 Parent Context。

## 6.6 embedding_profiles

```text
id
provider
model_name
dimension nullable
status                  # BUILDING/ACTIVE/FAILED/INACTIVE
created_at
activated_at nullable
```

## 6.7 chunk_embeddings

```text
id
chunk_id
embedding_profile_id
embedding vector        # 不强制固定维度，Demo 规模下优先兼容模型切换
created_at
```

同一个 Child Chunk 可同时拥有旧/新 embedding profile 的向量，支持“新索引未完成前继续使用旧索引”。

Demo 规模万级 Chunk 内，可以使用 exact cosine similarity，不强制 HNSW/IVFFlat，避免不同维度切换带来的索引复杂度。

## 6.8 conversations

```text
id
user_id
title
created_at
updated_at
```

## 6.9 messages

```text
id
conversation_id
role                 # USER/ASSISTANT
content
evidence_status      # SUFFICIENT/INSUFFICIENT/CONFLICTING
retrieval_meta JSONB
created_at
```

用户消息需记录本次查询所选择的知识库快照，可放 JSONB 或独立关联表；要求历史对话重新打开时仍能解释当时检索范围。

## 6.10 message_citations

```text
id
message_id
citation_index
document_id
document_version_id
chunk_id
quote_text
page_number nullable
heading_path
effective_date nullable
created_at
```

Citation 必须绑定具体文档版本，不允许只保存文件名字符串。

## 6.11 app_settings

仅保存非秘密配置：provider、模型名、endpoint、active_embedding_profile_id、reranker 开关等。API Key 只从 `.env` 读取。

## 6.12 Evaluation

可增加：

```text
evaluation_cases
evaluation_runs
evaluation_run_items
```

或者用 JSON + 结果文件保存，选更简洁但可追踪的方案。

---

# 7. 全局统计口径

禁止前端硬编码统计数据。

统一定义：

- “知识库”：当前登录用户可访问且未删除的知识库数量
- “总文档”：逻辑文档数量，不重复计算历史版本
- “可用文档”：当前版本 processing_status=READY 且 lifecycle_status=CURRENT 的逻辑文档数量
- “可检索片段”：当前 ACTIVE embedding profile 下、来自 CURRENT+READY 版本的 CHILD Chunk 数量
- “处理中”：当前版本处于 PARSING/CHUNKING/INDEXING 的逻辑文档数量
- “失败”：当前版本 processing_status=FAILED 的逻辑文档数量

Dashboard、知识库列表、详情、设置页的统计全部调用同一套后端统计服务。

页面显示统计刷新时间。

---

# 8. 文档与知识库状态机

## 8.1 文档版本 processing_status

```text
UPLOADED
→ PARSING
→ CHUNKING
→ INDEXING
→ READY
```

异常：

```text
FAILED
NEEDS_REINDEX
```

状态转换必须真实发生，不允许上传完成直接伪造 READY。

## 8.2 知识库聚合状态

根据当前版本聚合：

```text
EMPTY          无文档
READY          所有当前文档可用
UPDATING       至少一份处理中，仍有可用文档可检索
PARTIAL        至少一份 FAILED，但仍有可用文档
NEEDS_REINDEX  active embedding profile 变化后需要重建
```

例如 `UPDATING` 时 AI Chat 仍可搜索 READY 文档。

---

# 9. Document Pipeline

完整链路：

```text
Upload
→ Save original file
→ PARSING
→ Normalize document structure
→ CHUNKING
→ Parent / Child chunks
→ INDEXING
→ Embedding CHILD chunks
→ Save pgvector embedding
→ Invalidate/rebuild BM25 cache
→ READY
```

## 9.1 原始文件存储

首版本地存储即可：

```text
data/uploads/{user_id}/{knowledge_base_id}/{document_id}/{version_id}/source.ext
```

不加 OSS / MinIO。

## 9.2 Parser 接口

统一接口例如：

```text
DocumentParser
├─ PdfParser
├─ DocxParser
├─ MarkdownParser
└─ TextParser
```

全部转为统一 `NormalizedDocument` / `Section` 结构，后续 Chunking 不关心源格式。

### PDF

- 使用 PyMuPDF
- 保存 page_number
- 尽量识别标题/块
- 简单表格可使用 PyMuPDF table 能力或合理转换成 Markdown table
- 无有效文本：提示扫描 PDF 暂不支持 OCR

### DOCX

- 读取 Heading 1/2/3、段落
- 表格转 Markdown table

### Markdown

- 解析 `# / ## / ###`

### TXT

- 无结构时按段落 + token window 降级处理

---

# 10. Chunking

目标：结构感知 + Parent-Child Retrieval。

原则：**小块检索，大块生成。**

初始参数：

```text
Child ≈ 300～500 tokens（默认约 400）
Parent ≈ 800～1500 tokens（默认约 1000）
Child overlap ≈ 50 tokens，可配置
```

这些是默认工程参数，不得在 README 中声称是“最优值”。

有标题结构时按 Section/Heading 优先切分；无结构时采用递归/token-window。

每个 Child 必须保留：

```text
document_version_id
parent_id
heading_path
page_number
chunk_index
metadata
```

Parent 默认不需要 embedding。

---

# 11. Embedding 变更与 Reindex 闭环

Embedding 与 LLM 的切换逻辑不同。

LLM：可以热切换。

Embedding：更换后旧向量不能直接继续使用。

实现流程：

```text
用户选择新 Embedding
→ 后端计算影响范围
→ UI 展示受影响知识库/文档/片段
→ 用户确认“更换并重建索引”
→ 创建 BUILDING embedding_profile
→ 后台为全部有效 CHILD Chunk 生成新向量
→ 旧 ACTIVE profile 继续服务检索
→ 全部成功后原子切换新 profile 为 ACTIVE
→ 旧 profile 改 INACTIVE
→ 若失败：新 profile=FAILED，继续使用旧 ACTIVE profile
```

必须提供：

- 查看受影响知识库
- 重建索引进度
- 失败原因
- Retry
- “旧索引仍在使用”的状态提示

不需要实现复杂双版本手工回滚按钮，失败自动继续使用旧索引就是首版回滚策略。

文档处理可以使用 FastAPI BackgroundTasks 或应用内异步任务，不加 Celery/RabbitMQ。

---

# 12. Retrieval Pipeline

正常 AI Chat 默认流程：

```text
Question
→ Knowledge Base Scope validation（最多 5 个，或全部）
→ Active/current document version filter
→ Dense Retrieval Top 10
→ BM25 Top 10
→ RRF Fusion
→ Candidate Top 12
→ Reranker
→ Top 6
→ Parent Recovery
→ Parent dedupe
→ Final Context ≈ 4
→ Evidence Check
→ LLM generation
→ Citation mapping
→ SSE streaming answer
```

以上数字是默认参数，可在 Retrieval Lab 高级参数调整，不声称最优。

## 12.1 Dense

- Query embedding 与 CHILD embeddings cosine similarity
- 使用 pgvector
- Demo 规模允许 exact search

## 12.2 BM25

- `rank_bm25` + 中文分词（如 jieba）
- 每知识库或多知识库范围建立内存索引缓存
- 上传/删除/重建索引后 invalidate cache
- 只索引允许检索的 CHILD Chunk

## 12.3 RRF

使用 Reciprocal Rank Fusion 合并 Dense 与 BM25 排名。

注意：本项目使用 RRF，因此 UI **不要出现 alpha 权重参数**。

默认 `RRF constant = 60`，作为工程默认值，Lab 可调。

## 12.4 Reranker

首版使用现成预训练模型，不训练模型。

本地默认可用 CrossEncoder/BGE reranker；如果本地模型未准备好，可以关闭 Reranker，Hybrid 仍应可运行。

记录：

```text
RRF rank
Final rank
Rank delta
Reranker score
```

Retrieval Lab 要展示 `RRF #4 → Final #1 ↑ +3` 这种排名变化。

---

# 13. Evidence State

禁止显示“高可信”“可靠来源 96%”等无法校准的强结论。

状态统一：

```text
SUFFICIENT   已检索到相关资料
INSUFFICIENT 相关资料不足
CONFLICTING  发现来源信息不一致
```

基础判断：

- 无召回或 top result 低于可配置阈值 → INSUFFICIENT
- 多份当前有效资料在核心事实/数字/时间上出现明显冲突 → CONFLICTING
- 其余 → SUFFICIENT

冲突识别可以采用一个轻量、可解释的策略：

- 先基于检索结果的数字/日期/制度值进行简单一致性检查；
- 必要时使用 LLM 做结构化 evidence assessment；
- 不做复杂论文型 Self-RAG/CRAG。

无证据时 LLM 不得根据通用知识自由补答，应明确：“当前知识库中未找到足够信息支撑完整回答。”

---

# 14. Citation 与来源验证

Citation 是核心能力。

统一链路：

```text
Answer
→ [1][2]
→ Citation Card
→ 点击引用
→ Source Panel
→ 文档版本 + 章节 + 页码
→ 高亮 quote_text
→ 可查看上下文
```

Citation 固定展示字段：

```text
来源文档
制度版本
文件版本
生命周期状态（当前生效/历史版）
章节路径
页码
生效日期
```

普通 AI Chat 不显示 Chunk ID / score 等内部术语。

Retrieval Lab 才可以显示 Child Chunk、Parent Context、metadata、score。

Source Panel 使用解析后的原文文本即可完成高亮，不要求首版做 PDF Canvas 精准坐标渲染。

提供“打开原文件”入口。

---

# 15. LLM Provider

实现统一 Provider 接口：

```text
LLMProvider
├─ OllamaProvider
└─ OpenAICompatibleProvider
```

## Ollama

- 自动检测 `OLLAMA_BASE_URL`
- 调用 `/api/tags` 获取模型列表
- 如果存在 `qwen2.5:7b` 优先选择
- Windows FastAPI 本机运行时默认 `http://localhost:11434`

## OpenAI Compatible

从 `.env` 读取 base url/key/model。

Key 为空时 UI 显示“未配置”，不要报应用级异常。

设置页不回显完整 secret。

---

# 16. SSE Chat

必须实现流式回答。

前端体验至少包含：

```text
正在检索知识…
正在组织证据…
正在生成回答…
```

然后逐步输出 Markdown 内容。

SSE 中断需显示可重试状态。

对话历史记录：

- Conversation
- User/Assistant Messages
- 当时查询的 KB Scope
- Assistant Citations
- Retrieval metadata

重新打开历史对话时引用仍然可点击。

“重新生成”可以实现为低优先级功能；若实现，默认使用同一组检索证据，避免重新检索导致不可复现。

---

# 17. 财务 / 人事 / 合规类回答边界

如果引用来源来自 HR / Finance / Compliance 类知识库，在 Answer Footer 增加克制提示：

```text
依据当前生效资料生成
具体执行以制度原文及企业审批流程为准。
```

如果制度要求二次审批，回答中应保留该要求，不得简化成绝对结论。

不写长篇法律免责声明。

---

# 18. 页面功能要求

## 18.1 登录 / 注册

首版功能：

- 注册
- 登录
- JWT
- 密码 hash
- 密码至少 8 位，包含字母与数字
- 显示/隐藏密码
- Loading / Disabled / Error
- Remember me 可做本地 token 生命周期策略
- 服务协议/隐私政策占位页面可简单实现

不实现：

- 真正 SSO
- MFA
- 邮件找回密码

Future Work 中说明即可。

## 18.2 Dashboard

主操作：`新建知识库`

显示真实聚合：

- 知识库
- 可用文档 / 总文档
- 可检索片段
- 处理中数量
- 统计更新时间
- 最近知识库
- 最近对话

## 18.3 知识库列表

主操作：`新建知识库`

每卡：

- name
- description
- 总逻辑文档数
- 当前可检索片段
- 聚合状态
- 更新时间

搜索、编辑、删除。

三点菜单默认可 hover 出现，但键盘用户也能访问。

## 18.4 知识库详情

主操作：`上传文档`

Tabs：

- 文档
- 知识库设置

默认表格只展示 logical document 的当前版本；历史版本在 Document Inspector 的“版本历史”中查看，避免统计口径重复。

表格字段：

```text
文档名称
制度版本
文件版本
生效日期
状态
更新时间
```

Document Inspector：

- 文档信息
- 当前版本
- processing/lifecycle 状态
- Version History
- 解析概览
- 片段预览
- Reindex / Delete（必要时）

## 18.5 AI 问答

主操作：`新建对话`

- 左侧对话记录
- 最多选 5 个 KB
- 支持“全部知识库”
- 中央 Chat
- 中性 Evidence State
- 引用来源
- `查看检索过程` 默认折叠
- Source Panel 点击 Citation 打开
- Source Panel 中高亮原文

“查看检索过程”展开可显示：

```text
检索范围
Dense + BM25
RRF
Reranker
最终证据数
总检索耗时
```

不要把 score 常驻普通用户页面。

## 18.6 Retrieval Lab

Tabs：

- Single
- Compare
- Evaluation

Single：

- KB
- Question
- Dense/BM25/Hybrid/Hybrid+Reranker
- Advanced Params
- Run Retrieval
- Query Plan
- Stage Latency
- Result ranking
- Rank movement
- hit text
- hit keywords
- Parent Context expand
- Metadata

Score 必须写清类型：

```text
Dense Similarity
BM25 Score
RRF Rank
Reranker Score
```

不能统一叫“Score”假装同量纲。

Compare：至少能左右比较两种策略的 Top K。

Evaluation：运行 Golden Dataset 并显示真实结果。

## 18.7 设置

主操作：`保存更改`，并有“未保存更改”状态。

LLM：

```text
provider
部署方式
model
endpoint
status
测试连接
保存后立即生效
```

Embedding：

```text
provider/model
维度
影响范围
查看受影响知识库
更换并重建索引
重建进度
失败保护
```

Reranker：

```text
enable
provider/model
测试模型
保存后影响新请求
```

---

# 19. 全局 Empty / Loading / Error

建立公共状态组件。

至少覆盖：

```text
Loading
Empty
Error
No Result
Permission Denied
Model Offline
Index Failed
Retry
```

例：

空知识库：

```text
这个知识库还是空的
上传 PDF、DOCX、Markdown 或 TXT，即可开始构建知识索引。
[上传第一份文档]
```

Ollama 不可用：

```text
本地模型暂时不可用
无法连接 Ollama 服务。
[重新检测]
```

---

# 20. 时间与术语统一

前端统一时间格式工具：

```text
<1分钟     刚刚
今天        今天 10:24
昨天        昨天 17:30
最近7天     星期一 14:20
更早        YYYY-MM-DD HH:mm
```

Hover/title 显示完整 ISO 时间。

API 使用 offset-aware ISO 8601。

普通用户术语统一：

- 知识库
- 文档
- 可检索片段
- 上下文
- 引用来源

仅 Retrieval Lab 使用：

- Child Chunk
- Parent Context
- Dense
- BM25
- RRF
- Reranker

---

# 21. Demo Dataset

创建虚构企业：**NexaTech**。

创建 6 个知识库，逻辑文档总数约 24：

```text
人事制度库        4
财务制度库        5
产品知识库        4
客服知识库        3
采购管理库        4
信息安全库        4
```

文档内容全部为虚构演示数据，不引用真实公司机密或有版权的长文本。

至少包含：

- 员工手册
- 请假管理制度
- 年假制度
- 入离职流程
- 差旅管理制度（至少 V2.0 / V3.0 两个版本）
- 报销管理规范
- 发票开具说明
- 采购审批流程
- 供应商准入规范
- 合同审批流程
- 产品用户手册
- 产品售后规则
- 客户投诉处理
- 退款流程
- 信息安全管理制度
- 数据访问规范
- 应急响应流程

每份 Markdown Demo 文档建议带 YAML front matter，包含：

```yaml
title:
knowledge_base:
department:
category:
version:
file_version:
effective_date:
lifecycle_status:
```

Seed 时按 manifest 建立 logical document + version。

注意：UI 中的统计必须由真实 seed 后的数据库统计产生；设计图中的数字仅是视觉参考，不要求为了匹配截图去伪造固定 chunk 数。

---

# 22. Golden Dataset 与 Evaluation

创建约 **40 条**人工风格问题（可以程序生成初稿，但项目文件中应明确标注为 demo ground truth）。

每条至少：

```json
{
  "question": "...",
  "knowledge_base": "财务制度库",
  "expected_document": "差旅管理制度",
  "expected_version": "V3.0",
  "expected_heading": "第四章 > 住宿管理 > 二线城市"
}
```

核心评测：

```text
Recall@5
MRR
Average Retrieval Latency
```

比较：

```text
Dense
Hybrid
Hybrid + Reranker
```

可选加分：Faithfulness，但不是首版硬要求。

严禁伪造结果。

如果环境具备 embedding + reranker，实际运行并写入：

```text
docs/evaluation.md
README Evaluation Results
```

如果环境无法下载模型或无可用 provider，则留下可执行脚本和明确“Not Run”状态，不填假数字。

---

# 23. API 设计

至少提供以下 REST/SSE 能力，具体路径可按 REST 规范微调：

```text
/api/health
/api/auth/register
/api/auth/login
/api/auth/me

/api/knowledge-bases
/api/knowledge-bases/{id}
/api/knowledge-bases/{id}/stats
/api/knowledge-bases/{id}/documents

/api/documents/upload
/api/documents/{id}
/api/documents/{id}/versions
/api/document-versions/{id}/reindex
/api/document-versions/{id}/chunks

/api/conversations
/api/conversations/{id}
/api/conversations/{id}/messages
/api/chat/stream              # SSE

/api/retrieval/run
/api/retrieval/compare
/api/evaluation/run
/api/evaluation/runs/{id}

/api/settings
/api/settings/test-llm
/api/settings/test-reranker
/api/settings/embedding-impact
/api/settings/reindex
/api/settings/reindex-status

/api/ollama/models
```

Swagger 必须可用。

---

# 24. 测试

后端至少覆盖：

```text
Auth
KB ownership
Document version lifecycle
Parser
Chunking
Dense Retrieval
BM25
RRF
Hybrid Retrieval
Citation mapping
Embedding profile switch / fail-safe
Evidence insufficient state
```

不要追求 100% coverage，但核心链路必须测。

前端至少执行：

- TypeScript type check
- build
- 关键页面基本交互测试（如 Vitest/组件测试，按时间合理实现）

手动/脚本端到端验收链：

```text
注册
→ 登录
→ 创建知识库
→ 上传文本 PDF/DOCX/MD/TXT
→ 观察真实状态 UPLOADED/PARSING/CHUNKING/INDEXING/READY
→ 查看 Document Inspector
→ 提问
→ Hybrid Retrieval
→ Reranker
→ Parent Context
→ SSE Answer
→ Citation
→ 点击 Citation
→ Source Panel 高亮原文
→ Retrieval Lab
→ Evaluation
```

错误场景：

- 不支持格式
- 扫描 PDF
- Embedding 失败
- Ollama 未启动
- LLM API 未配置
- 无知识库
- 无检索结果
- Index failed
- SSE 中断

不允许白屏。

---

# 25. README

README 必须专业且真实，至少包含：

```text
InsightRAG 简介
核心能力
系统架构
UI Screenshots
Document Pipeline
RAG Pipeline
技术栈
项目目录
Quick Start
环境变量
Ollama 配置
Cloud Provider 配置
Demo Data
Retrieval Lab
Evaluation
设计取舍
已知限制
Future Work
```

必须说明：

- 本项目是 Demo/实习级验证规模，不宣称百万级生产检索；
- 默认 Demo 目标：单用户 <=10 KB、单 KB <=100 文档、Chunk 万级以内、单文件 <=30MB；
- PDF OCR 暂不支持；
- RRF + Reranker 等参数为默认工程参数，不宣称全局最优；
- Evaluation 数字全部来自实际运行。

生成架构图可以用 Mermaid，避免伪造复杂图片。

---

# 26. Git 与 GitHub（必须执行）

项目必须纳入 Git 并上传 GitHub。

默认仓库名：

```text
insight-rag
```

默认分支：

```text
main
```

建议公开仓库（用于求职展示）。如果当前远程仓库已经存在，以现有 remote 为准，不重复创建。

执行前：

1. 生成严格 `.gitignore`
2. 检查 `.env`、API key、JWT secret、uploads、database volume、model cache、node_modules、venv、IDE cache 未被追踪
3. 使用 `git status` 和必要的 secret grep 检查
4. README 不得出现真实密钥

提交策略不需要几十个碎 commit，但应至少有清晰里程碑，例如：

```text
feat: scaffold InsightRAG application
feat: add document ingestion and versioning
feat: implement hybrid retrieval pipeline
feat: add chat citations and retrieval lab
test: add evaluation and core test coverage
docs: finalize README and demo documentation
```

最终：

- 如果 `gh auth status` 成功：
  - 若无仓库：`gh repo create insight-rag --public --source . --remote origin --push`
  - 若已有仓库：设置/确认 remote 后 push main
- 如果没有 GitHub CLI，但 git remote 已配置：直接 `git push -u origin main`
- 如果机器没有任何 GitHub 授权：不要影响项目其它部分完成；最后只在这一项要求用户完成授权，然后立即执行 push。GitHub push 是最终交付步骤之一。

推送成功后，在 README 顶部保留简洁项目说明，不加入虚假 star/build badge。

---

# 27. 内部 Phase 施工顺序（自动连续执行）

这些 Phase 只用于你自己组织工作，不要向用户逐阶段索要确认。

## Phase 0 — Scaffold

- repo structure
- Docker PostgreSQL+pgvector
- FastAPI health
- Vue shell
- DB connection
- `.env.example`

验收：Swagger / frontend / DB 均启动。

## Phase 1 — Auth + KB

- Register/Login/JWT
- KB CRUD
- ownership
- Dashboard real stats

## Phase 2 — Document + Version + Parser

- upload/local storage
- logical doc + version model
- PDF/DOCX/MD/TXT parser
- status machine
- Document Inspector

## Phase 3 — Chunk + Embedding + Dense

- parent/child
- embedding profile
- chunk_embeddings
- dense retrieval baseline

## Phase 4 — BM25 + RRF + Hybrid

- Chinese BM25
- cache invalidation
- hybrid retrieval
- Retrieval Lab basic

## Phase 5 — Reranker + Parent + Citation

- rerank
- rank delta
- parent recovery
- citation mapping
- source panel

## Phase 6 — Chat + SSE + Evidence

- multi KB max 5 / all KB
- SSE
- history
- evidence states
- HR/Finance footer

## Phase 7 — Retrieval Lab + Evaluation

- Single/Compare/Evaluation
- Query Plan
- stage latency
- Golden Dataset
- Recall@5/MRR/latency

## Phase 8 — Polish + Test + Docs + GitHub

- all UI states
- accessibility basics
- responsive boundaries
- tests/build
- README
- demo seed
- real evaluation if environment allows
- git commits
- GitHub push

---

# 28. 最终验收清单（必须全部检查）

1. 所有页面统计来自统一后端服务，无互相矛盾硬编码数字。
2. Document / DocumentVersion / Citation 关系正确，历史版本与当前生效版可区分。
3. Knowledge Base 聚合状态与真实文档状态一致。
4. 无证据 / 证据不足 / 来源冲突均有对应 UI。
5. Citation 可定位文档 → 版本 → 章节 → 页码 → 高亮原文。
6. Embedding 变更具备影响检查、新索引重建、进度、失败保护，旧索引在切换前可继续服务。
7. LLM / Embedding / Reranker 设置具备测试、保存和生效反馈。
8. Auth 具备安全密码存储、密码策略、错误态、Loading/Disabled。
9. Retrieval Lab 展示 Query Plan、真实策略参数、阶段耗时、排名变化。
10. 所有异步操作均有 Loading / Empty / Error / Retry。
11. 可操作元素具备 hover/focus/keyboard 基础支持，状态不只靠颜色表达。
12. Demo 日期和统计均来自真实 seed 数据和系统时间，不保留 2024 占位数据。
13. 云端 API Key 缺失不会阻塞项目启动或开发。
14. `.env` 和 secrets 未进入 Git history。
15. `pytest`、frontend build/typecheck 通过。
16. README 与实际实现一致，不夸大能力。
17. Evaluation 不伪造数字。
18. 项目已成功推送到 GitHub `main` 分支（若机器授权正常）。

---

# 29. Definition of Done

只有满足以下两条完整链路，项目才算完成。

## 用户链

```text
注册
→ 登录
→ 新建知识库
→ 上传 PDF/DOCX/MD/TXT
→ 状态真实变化
→ 解析/切片/Embedding/索引完成
→ 选择一个或多个知识库
→ 提问
→ Hybrid Retrieval + RRF + Reranker
→ Parent Context
→ SSE 回答
→ Citation
→ 点击来源
→ 查看版本/章节/页码/高亮原文
```

## 开发者链

```text
进入 Retrieval Lab
→ 输入同一问题
→ Dense/BM25/Hybrid/Hybrid+Reranker
→ Query Plan
→ 阶段耗时
→ 查看排名变化
→ 展开 Parent Context / Metadata
→ 运行 Golden Dataset
→ 得到 Recall@5 / MRR / Latency（环境允许）
```

两条链都通过后，再执行最终 GitHub push。

---

# 30. 最终交付回复格式

全部完成后，不要写空泛“项目基本完成”。请给用户明确汇报：

```text
1. 项目路径
2. GitHub 仓库地址
3. 启动方式
4. 默认 Demo 账号（如创建）
5. Ollama 检测结果与实际使用模型
6. Cloud API 仍需用户在 .env 填写的变量
7. 数据库/端口
8. 已通过的测试
9. Evaluation 是否已真实运行及结果文件位置
10. 当前已知限制
11. 关键页面完成情况
12. git status 是否 clean / 最终 commit hash
```

若某个外部环境能力未完成（如网络导致模型无法下载），必须如实写明，不得用假数据掩盖。

---

## 最后强调

- 不暂停等待用户填写模型 API Key；只创建 `.env.example`，用户后续自行填写。
- 不擅自扩大技术范围。
- 不伪造任何“企业级性能”或评测数字。
- 不牺牲代码可读性去追求过度复杂架构。
- UI 布局/风格以提供的 8 张 V2 设计图为基准，但真实数据语义和正确性高于截图中的示例文字。
- 完成前持续自动验证与修复。
- 最终必须整理并上传 GitHub。
