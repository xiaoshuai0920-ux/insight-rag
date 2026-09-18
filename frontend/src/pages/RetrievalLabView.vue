<template>
  <div>
    <div class="hero">
      <h1 class="hero-title">Retrieval Lab</h1>
      <p class="hero-sub">分析不同检索策略的召回效果与排序变化</p>
    </div>

    <div class="tabs-bar" role="tablist">
      <button
        v-for="t in tabs"
        :key="t.key"
        class="tab-btn"
        :class="{ active: activeTab === t.key }"
        role="tab"
        :aria-selected="activeTab === t.key"
        @click="activeTab = t.key as any"
      >
        {{ t.label }}
      </button>
    </div>

    <!-- ===================== Single ===================== -->
    <div v-show="activeTab === 'single'">
      <div class="card config-card">
        <h3 class="card-title">检索配置</h3>
        <div class="config-row">
          <div class="cfg-field">
            <label class="cfg-label">知识库</label>
            <el-select v-model="form.kbIds" multiple :multiple-limit="5" placeholder="全部知识库" style="width: 100%" clearable>
              <el-option v-for="kb in kbs" :key="kb.id" :label="kb.name" :value="kb.id" />
            </el-select>
          </div>
          <div class="cfg-field grow">
            <label class="cfg-label">问题</label>
            <div class="q-wrap">
              <input v-model="form.question" class="q-input" type="text" placeholder="输入要测试的问题…" @keydown.enter="run" />
              <button v-if="form.question" class="q-clear" aria-label="清空问题" @click="form.question = ''">✕</button>
            </div>
          </div>
          <div class="cfg-field">
            <label class="cfg-label">检索策略</label>
            <div class="strategy-group" role="radiogroup" aria-label="检索策略">
              <button
                v-for="s in strategies"
                :key="s.value"
                class="strategy-btn"
                :class="{ active: form.strategy === s.value }"
                role="radio"
                :aria-checked="form.strategy === s.value"
                @click="form.strategy = s.value"
              >
                {{ s.label }}
              </button>
            </div>
          </div>
        </div>

        <details class="advanced" :open="advancedOpen" @toggle="advancedOpen = ($event.target as HTMLDetailsElement).open">
          <summary>∨ 高级参数</summary>
          <div class="adv-grid">
            <div v-for="p in advancedParams" :key="p.key" class="adv-field">
              <label class="cfg-label" :title="p.tip">{{ p.label }} <span class="tip-icon" :title="p.tip">ⓘ</span></label>
              <el-input-number v-model="form[p.key]" :min="p.min" :max="p.max" size="default" style="width: 100%" />
            </div>
            <div class="adv-field adv-run">
              <button class="btn-primary run-btn" :disabled="running || !form.question.trim()" @click="run">
                <span v-if="running" class="spinner"></span>
                <span v-else aria-hidden="true">▶</span>
                {{ running ? '检索中…' : 'Run Retrieval' }}
              </button>
            </div>
          </div>
        </details>
      </div>

      <!-- Query Plan -->
      <div v-if="result" class="card plan-card">
        <div class="plan-head">
          <div>
            <h3 class="card-title">Query Plan</h3>
            <p class="card-hint">检索执行流程与耗时分析</p>
          </div>
          <div class="plan-total">
            <div class="plan-total-label">总耗时</div>
            <div class="plan-total-value">{{ Math.round(result.total_latency_ms) }} ms</div>
          </div>
        </div>
        <div class="plan-flow">
          <template v-for="(step, i) in planSteps" :key="i">
            <div class="plan-node" :class="`plan-${step.step}`">
              <div class="plan-node-icon" aria-hidden="true">{{ step.icon }}</div>
              <div class="plan-node-label">{{ step.label }}</div>
              <div class="plan-node-detail">{{ step.detail }}</div>
            </div>
            <div v-if="i < planSteps.length - 1" class="plan-arrow" aria-hidden="true">→</div>
          </template>
        </div>
        <div class="plan-latencies">
          <span class="plan-latency-label">各阶段耗时 ⓘ（悬停查看定义）</span>
          <div class="latency-chips">
            <span v-for="s in result.stages" :key="s.stage" class="latency-chip" :class="`lat-${s.stage}`">
              <span class="lat-dot" aria-hidden="true"></span>{{ s.label }}
              <b>{{ s.latency_ms }}ms</b>
            </span>
          </div>
        </div>
        <div v-if="result.reranker_error" class="plan-warning">ℹ {{ result.reranker_error }}</div>
      </div>

      <!-- Results -->
      <div v-if="result" class="card results-card">
        <div class="results-head">
          <h3 class="card-title">检索结果</h3>
          <span class="results-count">共 {{ result.hits.length }} 条结果（显示 Top {{ result.hits.length }}）</span>
        </div>

        <div v-for="hit in result.hits" :key="hit.chunk_id" class="result-row">
          <div class="result-rank" :class="{ top: hit.final_rank <= 3 }">{{ hit.final_rank }}</div>
          <div class="result-main">
            <div class="result-title-row">
              <span class="result-doc-title">
                <span class="doc-icon" aria-hidden="true">📄</span>{{ hit.document_title }}
              </span>
              <StatusBadge
                :status="hit.lifecycle_status"
                :label="hit.lifecycle_status === 'HISTORICAL' ? '历史版' : '当前生效'"
              />
              <span class="meta-chip">{{ hit.version_label }}</span>
              <span class="result-path">{{ hit.heading_path }}</span>
            </div>
            <p class="result-snippet">{{ hit.content }}</p>
            <div class="result-keywords" v-if="hit.hit_keywords?.length">
              命中关键词：
              <span v-for="k in hit.hit_keywords" :key="k" class="kw-chip">{{ k }}</span>
            </div>
          </div>
          <div class="result-side">
            <div class="rank-move" :class="moveClass(hit.rank_delta)">
              RRF #{{ hit.rrf_rank ?? '-' }} → Final #{{ hit.final_rank }}
              {{ deltaText(hit.rank_delta) }}
            </div>
            <div class="scores">
              <div v-if="hit.reranker_score !== null && hit.reranker_score !== undefined" class="score-box">
                <div class="score-label">Reranker Score</div>
                <div class="score-value">{{ hit.reranker_score.toFixed(4) }}</div>
              </div>
              <div v-if="hit.dense_similarity !== null && hit.dense_similarity !== undefined" class="score-box">
                <div class="score-label">Dense Similarity</div>
                <div class="score-value">{{ hit.dense_similarity.toFixed(4) }}</div>
              </div>
              <div v-if="hit.bm25_score !== null && hit.bm25_score !== undefined" class="score-box">
                <div class="score-label">BM25 Score</div>
                <div class="score-value">{{ hit.bm25_score.toFixed(3) }}</div>
              </div>
            </div>
            <div class="result-accordion">
              <details>
                <summary>展开父级上下文</summary>
                <p class="accordion-text">{{ hit.parent_content || hit.content }}</p>
              </details>
              <details>
                <summary>查看元数据</summary>
                <pre class="meta-json">{{ metaJson(hit) }}</pre>
              </details>
            </div>
          </div>
        </div>

        <EmptyState
          v-if="!result.hits.length"
          icon="🔍"
          title="没有检索结果"
          description="尝试更换问题表述、扩大知识库范围，或确认文档已完成索引。"
        />
      </div>
    </div>

    <!-- ===================== Compare ===================== -->
    <div v-show="activeTab === 'compare'">
      <div class="card config-card">
        <h3 class="card-title">策略对比</h3>
        <div class="config-row">
          <div class="cfg-field grow">
            <label class="cfg-label">问题</label>
            <div class="q-wrap">
              <input v-model="form.question" class="q-input" type="text" placeholder="输入要对比的同一问题…" />
            </div>
          </div>
          <div class="cfg-field">
            <label class="cfg-label">知识库</label>
            <el-select v-model="form.kbIds" multiple :multiple-limit="5" placeholder="全部知识库" style="width: 100%" clearable>
              <el-option v-for="kb in kbs" :key="kb.id" :label="kb.name" :value="kb.id" />
            </el-select>
          </div>
          <div class="adv-field adv-run compare-run">
            <button class="btn-primary run-btn" :disabled="running || !form.question.trim()" @click="runCompare">
              <span v-if="running" class="spinner"></span>
              {{ running ? '对比中…' : 'Run Compare' }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="compareResult" class="compare-grid">
        <div v-for="side in ['dense', 'hybrid']" :key="side" class="card compare-card">
          <div class="compare-head">
            <h3 class="card-title">{{ side === 'dense' ? 'Dense 向量检索' : 'Hybrid + RRF' }}</h3>
            <span class="compare-latency">{{ Math.round(compareResult[side].total_latency_ms) }} ms</span>
          </div>
          <div v-for="hit in compareResult[side].hits.slice(0, 5)" :key="hit.chunk_id" class="compare-row">
            <div class="result-rank sm" :class="{ top: hit.final_rank <= 3 }">{{ hit.final_rank }}</div>
            <div class="compare-main">
              <div class="compare-title">{{ hit.document_title }} · {{ hit.heading_path }}</div>
              <p class="compare-snippet">{{ hit.content }}</p>
            </div>
          </div>
          <EmptyState v-if="!compareResult[side].hits.length" icon="∅" title="无结果" />
        </div>
      </div>
    </div>

    <!-- ===================== Evaluation ===================== -->
    <div v-show="activeTab === 'evaluation'">
      <div class="card config-card">
        <div class="eval-head">
          <div>
            <h3 class="card-title">Golden Dataset 评测</h3>
            <p class="card-hint">
              使用 demo-data/golden-dataset.json 中的人工标注问题集，运行真实检索并计算 Recall@5 / MRR / 平均延迟。结果不做任何伪造。
            </p>
          </div>
          <div class="eval-controls">
            <el-select v-model="evalStrategy" style="width: 180px">
              <el-option label="Dense" value="dense" />
              <el-option label="BM25" value="bm25" />
              <el-option label="Hybrid" value="hybrid" />
              <el-option label="Hybrid + Reranker" value="hybrid_rerank" />
            </el-select>
            <button class="btn-primary run-btn" :disabled="evalRunning" @click="runEvaluation">
              <span v-if="evalRunning" class="spinner"></span>
              {{ evalRunning ? '评测运行中…' : '运行评测' }}
            </button>
          </div>
        </div>
        <div v-if="evalError" class="plan-warning">ℹ {{ evalError }}</div>
      </div>

      <div v-if="latestRun" class="card eval-result-card">
        <div class="eval-metrics">
          <div class="metric-box">
            <div class="metric-label">Recall@5</div>
            <div class="metric-value">{{ pct(latestRun.recall_at_5) }}</div>
          </div>
          <div class="metric-box">
            <div class="metric-label">MRR</div>
            <div class="metric-value">{{ latestRun.mrr?.toFixed(3) ?? 'N/A' }}</div>
          </div>
          <div class="metric-box">
            <div class="metric-label">平均检索延迟</div>
            <div class="metric-value">{{ Math.round(latestRun.avg_latency_ms || 0) }} <small>ms</small></div>
          </div>
          <div class="metric-box">
            <div class="metric-label">策略 / 样本</div>
            <div class="metric-value metric-value-sm">{{ latestRun.strategy }} / {{ latestRun.total_cases }}</div>
          </div>
        </div>
        <div class="eval-table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>问题</th>
                <th>期望文档</th>
                <th>命中</th>
                <th>排名</th>
                <th>延迟</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, i) in latestRun.detail?.cases || []" :key="i">
                <td class="eval-q">{{ item.question }}</td>
                <td>{{ item.expected_document }}</td>
                <td>
                  <StatusBadge :status="item.hit ? 'READY' : 'FAILED'" :label="item.hit ? 'HIT' : 'MISS'" />
                </td>
                <td>{{ item.rank ?? '-' }}</td>
                <td>{{ item.latency_ms != null ? Math.round(item.latency_ms) + 'ms' : '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="evalRuns.length" class="card history-card">
        <h3 class="card-title">历史评测记录</h3>
        <div v-for="run in evalRuns" :key="run.id" class="history-row" @click="latestRun = run">
          <span class="history-strategy">{{ run.strategy }}</span>
          <span class="history-metric">Recall@5 {{ pct(run.recall_at_5) }}</span>
          <span class="history-metric">MRR {{ run.mrr?.toFixed(3) ?? 'N/A' }}</span>
          <span class="history-time">{{ formatTime(run.created_at) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { kbApi, labApi, type KnowledgeBase } from '../api'
import { formatTime } from '../utils/format'
import StatusBadge from '../components/StatusBadge.vue'
import EmptyState from '../components/EmptyState.vue'

const tabs = [
  { key: 'single', label: 'Single' },
  { key: 'compare', label: 'Compare' },
  { key: 'evaluation', label: 'Evaluation' },
]
const activeTab = ref<'single' | 'compare' | 'evaluation'>('single')

const kbs = ref<KnowledgeBase[]>([])
const running = ref(false)
const result = ref<any>(null)
const compareResult = ref<any>(null)

const strategies = [
  { label: 'Dense', value: 'dense' },
  { label: 'BM25', value: 'bm25' },
  { label: 'Hybrid', value: 'hybrid' },
  { label: 'Hybrid + Reranker', value: 'hybrid_rerank' },
]

const form = reactive({
  kbIds: [] as number[],
  question: '成都普通员工住宿标准是多少？',
  strategy: 'hybrid_rerank',
  dense_top_k: 10,
  bm25_top_k: 10,
  rrf_candidate_k: 12,
  rrf_constant: 60,
  reranker_top_k: 6,
  final_context: 4,
})

const advancedParams = [
  { key: 'dense_top_k', label: 'Dense Top K', min: 1, max: 50, tip: '向量检索召回的片段数' },
  { key: 'bm25_top_k', label: 'BM25 Top K', min: 1, max: 50, tip: '关键词检索召回的片段数' },
  { key: 'rrf_candidate_k', label: 'RRF Candidate K', min: 1, max: 100, tip: 'RRF 融合后保留的候选数' },
  { key: 'rrf_constant', label: 'RRF Constant', min: 1, max: 200, tip: 'RRF 平滑常数，默认 60' },
  { key: 'reranker_top_k', label: 'Reranker Top K', min: 1, max: 50, tip: '重排后保留的片段数' },
  { key: 'final_context', label: 'Final Context', min: 1, max: 20, tip: '最终送入生成环节的证据数' },
] as const

const advancedOpen = ref(false)

const planSteps = computed(() => {
  if (!result.value) return []
  const icons: Record<string, string> = { query: '💬', dense: '🧲', bm25: '🔤', rrf: '🔀', rerank: '🧮', parent: '📚', final: '✅' }
  return (result.value.plan || []).map((p: any) => ({
    ...p,
    icon: icons[p.step] || '•',
  }))
})

function moveClass(delta: number) {
  if (delta > 0) return 'up'
  if (delta < 0) return 'down'
  return 'flat'
}

function deltaText(delta: number) {
  if (delta > 0) return `↑ +${delta}`
  if (delta < 0) return `↓ ${delta}`
  return '—'
}

function metaJson(hit: any) {
  return JSON.stringify(
    {
      chunk_id: hit.chunk_id,
      chunk_type: hit.chunk_type,
      document_version_id: hit.document_version_id,
      kb: hit.kb_name,
      heading_path: hit.heading_path,
      page_number: hit.page_number,
      scores: {
        dense_similarity: hit.dense_similarity,
        bm25_score: hit.bm25_score,
        rrf_rank: hit.rrf_rank,
        rrf_score: hit.rrf_score,
        reranker_score: hit.reranker_score,
      },
    },
    null,
    2,
  )
}

async function run() {
  running.value = true
  result.value = null
  try {
    result.value = await labApi.run({
      kb_ids: form.kbIds.length ? form.kbIds : null,
      question: form.question,
      strategy: form.strategy,
      dense_top_k: form.dense_top_k,
      bm25_top_k: form.bm25_top_k,
      rrf_candidate_k: form.rrf_candidate_k,
      rrf_constant: form.rrf_constant,
      reranker_top_k: form.reranker_top_k,
      final_context: form.final_context,
    })
  } catch (err: any) {
    ElMessage.error(err.message || '检索失败')
  } finally {
    running.value = false
  }
}

async function runCompare() {
  running.value = true
  compareResult.value = null
  try {
    compareResult.value = await labApi.compare({
      kb_ids: form.kbIds.length ? form.kbIds : null,
      question: form.question,
      strategy: 'hybrid',
      final_context: 5,
    })
  } catch (err: any) {
    ElMessage.error(err.message || '对比失败')
  } finally {
    running.value = false
  }
}

// Evaluation
const evalStrategy = ref('hybrid')
const evalRunning = ref(false)
const evalError = ref('')
const latestRun = ref<any>(null)
const evalRuns = ref<any[]>([])

function pct(v: number | null | undefined) {
  if (v === null || v === undefined) return 'N/A'
  return `${(v * 100).toFixed(1)}%`
}

async function runEvaluation() {
  evalRunning.value = true
  evalError.value = ''
  try {
    latestRun.value = await labApi.evaluationRun(evalStrategy.value)
    await loadEvalRuns()
    ElMessage.success('评测完成')
  } catch (err: any) {
    evalError.value = err.message || '评测失败'
  } finally {
    evalRunning.value = false
  }
}

async function loadEvalRuns() {
  try {
    evalRuns.value = await labApi.evaluationRuns()
  } catch {
    /* ignore */
  }
}

onMounted(async () => {
  kbs.value = await kbApi.list()
  loadEvalRuns()
})
</script>

<style scoped>
.hero { margin-bottom: 16px; }
.hero-title { font-size: 22px; font-weight: 800; margin: 0 0 4px; }
.hero-sub { color: var(--text-secondary); margin: 0; font-size: 13px; }
.tabs-bar { display: flex; gap: 4px; margin-bottom: 16px; border-bottom: 1px solid var(--border); }
.tab-btn {
  border: none; background: transparent; cursor: pointer; font-size: 14px;
  padding: 10px 18px; color: var(--text-secondary); border-bottom: 2px solid transparent;
  margin-bottom: -1px; font-weight: 500;
}
.tab-btn:hover { color: var(--text); }
.tab-btn.active { color: var(--primary); border-bottom-color: var(--primary); font-weight: 700; }
.config-card { padding: 20px 22px; margin-bottom: 16px; }
.card-title { margin: 0 0 6px; font-size: 15px; font-weight: 700; }
.card-hint { color: var(--text-secondary); font-size: 12.5px; margin: 0; }
.config-row { display: flex; gap: 16px; margin-top: 14px; align-items: flex-end; flex-wrap: wrap; }
.cfg-field { min-width: 170px; }
.cfg-field.grow { flex: 1; min-width: 260px; }
.cfg-label { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px; font-weight: 600; }
.tip-icon { color: var(--text-tertiary); cursor: help; }
.q-wrap { display: flex; align-items: center; border: 1px solid var(--border); border-radius: 8px; padding: 0 12px; background: #fff; }
.q-wrap:focus-within { border-color: var(--primary); }
.q-input { flex: 1; border: none; outline: none; padding: 10px 0; font-size: 13.5px; background: transparent; }
.q-clear { border: none; background: transparent; cursor: pointer; color: var(--text-tertiary); }
.strategy-group { display: flex; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
.strategy-btn {
  border: none; background: #fff; cursor: pointer; font-size: 12.5px;
  padding: 9px 14px; color: var(--text-secondary); border-right: 1px solid var(--border);
  white-space: nowrap;
}
.strategy-btn:last-child { border-right: none; }
.strategy-btn:hover { background: #f7f8fa; }
.strategy-btn.active { background: var(--primary-light); color: var(--primary); font-weight: 700; }
.advanced { margin-top: 14px; border-top: 1px dashed var(--border); padding-top: 12px; }
.advanced summary { cursor: pointer; color: var(--text-secondary); font-size: 13px; user-select: none; }
.adv-grid { display: grid; grid-template-columns: repeat(6, 1fr) auto; gap: 12px; margin-top: 12px; align-items: end; }
.adv-field label { display: block; font-size: 11.5px; color: var(--text-secondary); margin-bottom: 4px; }
.run-btn { padding: 10px 22px; white-space: nowrap; }
.compare-run { margin-left: auto; }
.spinner {
  width: 13px; height: 13px; border: 2px solid rgba(255,255,255,0.4); border-top-color: #fff;
  border-radius: 50%; animation: spin 0.7s linear infinite; display: inline-block;
  margin-right: 4px; vertical-align: -2px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.plan-card { padding: 20px 22px; margin-bottom: 16px; }
.plan-head { display: flex; justify-content: space-between; align-items: flex-start; }
.plan-total { text-align: right; }
.plan-total-label { font-size: 11.5px; color: var(--text-tertiary); }
.plan-total-value { font-size: 22px; font-weight: 800; }
.plan-flow {
  display: flex; align-items: stretch; gap: 8px; margin-top: 16px; flex-wrap: wrap;
}
.plan-node {
  border: 1px solid var(--border); border-radius: 10px; padding: 10px 14px;
  min-width: 108px; text-align: center; background: #fafbfc; flex: 1;
}
.plan-node-icon { font-size: 16px; margin-bottom: 4px; }
.plan-node-label { font-weight: 700; font-size: 12.5px; }
.plan-node-detail { font-size: 11px; color: var(--text-tertiary); margin-top: 3px; }
.plan-arrow { align-self: center; color: var(--text-tertiary); }
.plan-latencies { margin-top: 16px; }
.plan-latency-label { font-size: 12px; color: var(--text-secondary); font-weight: 600; }
.latency-chips { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
.latency-chip {
  display: inline-flex; align-items: center; gap: 6px;
  background: #f5f6f8; border-radius: 999px; padding: 4px 12px; font-size: 12px;
}
.latency-chip b { font-weight: 700; }
.lat-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.lat-scope .lat-dot { background: #94a3b8; }
.lat-embed .lat-dot { background: #818cf8; }
.lat-dense .lat-dot { background: #6366f1; }
.lat-bm25 .lat-dot { background: #10b981; }
.lat-fusion .lat-dot { background: #8b5cf6; }
.lat-rerank .lat-dot { background: #f59e0b; }
.lat-hydrate .lat-dot { background: #64748b; }
.lat-parent .lat-dot { background: #14b8a6; }
.plan-warning {
  margin-top: 14px; background: var(--amber-bg); color: var(--amber);
  border-radius: 8px; padding: 9px 14px; font-size: 12.5px;
}
.results-card { padding: 20px 22px; }
.results-head { display: flex; align-items: baseline; gap: 12px; margin-bottom: 14px; }
.results-count { font-size: 12px; color: var(--text-tertiary); }
.result-row {
  display: flex; gap: 14px; padding: 16px 0; border-top: 1px solid #f3f4f6;
}
.result-rank {
  width: 34px; height: 34px; border-radius: 9px; background: #f3f4f6;
  display: flex; align-items: center; justify-content: center;
  font-weight: 800; font-size: 14px; flex-shrink: 0; color: var(--text-secondary);
}
.result-rank.top { background: var(--primary-light); color: var(--primary); }
.result-rank.sm { width: 26px; height: 26px; font-size: 12px; }
.result-main { flex: 1; min-width: 0; }
.result-title-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.result-doc-title { font-weight: 700; font-size: 14px; display: inline-flex; align-items: center; gap: 6px; }
.meta-chip {
  font-size: 11px; background: #f3f4f6; border: 1px solid var(--border);
  border-radius: 5px; padding: 1px 7px; color: var(--text-secondary);
}
.result-path { font-size: 12px; color: var(--text-tertiary); }
.result-snippet {
  font-size: 13px; color: var(--text-secondary); line-height: 1.7; margin: 8px 0;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.result-keywords { font-size: 12px; color: var(--text-tertiary); }
.kw-chip {
  background: var(--primary-light); color: var(--primary); border-radius: 5px;
  padding: 1px 7px; margin-left: 5px; font-size: 11.5px; font-weight: 600;
}
.result-side { width: 300px; flex-shrink: 0; display: flex; flex-direction: column; gap: 10px; }
.rank-move { font-size: 12px; font-weight: 700; }
.rank-move.up { color: var(--green); }
.rank-move.down { color: var(--red); }
.rank-move.flat { color: var(--text-tertiary); }
.scores { display: flex; gap: 8px; flex-wrap: wrap; }
.score-box {
  border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; min-width: 86px;
}
.score-label { font-size: 10.5px; color: var(--text-tertiary); }
.score-value { font-size: 15px; font-weight: 800; }
.result-accordion details { margin-bottom: 6px; }
.result-accordion summary {
  cursor: pointer; font-size: 12px; color: var(--primary); user-select: none; font-weight: 600;
}
.accordion-text { font-size: 12.5px; color: var(--text-secondary); line-height: 1.7; margin: 8px 0 0; }
.meta-json {
  font-size: 11.5px; background: #f7f8fa; border-radius: 8px; padding: 10px;
  overflow-x: auto; line-height: 1.6;
}
.compare-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.compare-card { padding: 18px 20px; }
.compare-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; }
.compare-latency { font-size: 13px; font-weight: 700; color: var(--text-secondary); }
.compare-row { display: flex; gap: 10px; padding: 10px 0; border-top: 1px solid #f3f4f6; }
.compare-main { flex: 1; min-width: 0; }
.compare-title { font-size: 13px; font-weight: 600; }
.compare-snippet {
  font-size: 12px; color: var(--text-tertiary); margin: 4px 0 0; line-height: 1.6;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.eval-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.eval-controls { display: flex; gap: 10px; align-items: center; }
.eval-result-card { padding: 20px 22px; margin-top: 16px; }
.eval-metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.metric-box {
  border: 1px solid var(--border); border-radius: 10px; padding: 14px 18px;
  background: #fafbfc;
}
.metric-label { font-size: 11.5px; color: var(--text-tertiary); }
.metric-value { font-size: 22px; font-weight: 800; margin-top: 4px; }
.metric-value small { font-size: 12px; font-weight: 400; }
.metric-value-sm { font-size: 16px; }
.eval-table-wrap { max-height: 420px; overflow-y: auto; }
.eval-q { max-width: 340px; }
.history-card { padding: 18px 22px; margin-top: 16px; }
.history-row {
  display: flex; gap: 18px; padding: 10px 4px; border-top: 1px solid #f3f4f6;
  cursor: pointer; font-size: 13px; align-items: center;
}
.history-row:hover { background: #fafbfc; }
.history-strategy { font-weight: 700; min-width: 110px; }
.history-metric { color: var(--text-secondary); }
.history-time { margin-left: auto; color: var(--text-tertiary); font-size: 12px; }
@media (max-width: 1279px) {
  .adv-grid { grid-template-columns: repeat(3, 1fr); }
  .result-side { width: 240px; }
  .compare-grid, .eval-metrics { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 767px) {
  .adv-grid { grid-template-columns: 1fr 1fr; }
  .result-row { flex-direction: column; }
  .result-side { width: 100%; }
  .compare-grid, .eval-metrics { grid-template-columns: 1fr; }
}
</style>
