<template>
  <div>
    <div class="hero">
      <h1 class="hero-title">知识工作台</h1>
      <p class="hero-sub">统一管理企业知识、检索状态与最近问答</p>
    </div>

    <div v-if="loading" class="stats-grid">
      <div v-for="i in 4" :key="i" class="stat-card card"><div class="skeleton-block" /></div>
    </div>
    <div v-else class="stats-grid">
      <div class="stat-card card">
        <div class="stat-icon stat-icon-blue" aria-hidden="true">📖</div>
        <div>
          <div class="stat-label">知识库</div>
          <div class="stat-value">{{ stats?.summary.knowledge_bases ?? '-' }}</div>
        </div>
      </div>
      <div class="stat-card card">
        <div class="stat-icon stat-icon-green" aria-hidden="true">📄</div>
        <div>
          <div class="stat-label">可用文档</div>
          <div class="stat-value">
            {{ stats?.summary.available_documents ?? '-' }} /
            {{ stats?.summary.total_documents ?? '-' }}
          </div>
        </div>
      </div>
      <div class="stat-card card">
        <div class="stat-icon stat-icon-indigo" aria-hidden="true">🗂</div>
        <div>
          <div class="stat-label">可检索片段</div>
          <div class="stat-value">{{ formatNumber(stats?.summary.retrievable_chunks) }}</div>
        </div>
      </div>
      <div class="stat-card card">
        <div class="stat-icon stat-icon-amber" aria-hidden="true">⏳</div>
        <div>
          <div class="stat-label">索引状态</div>
          <div class="stat-value stat-value-sm">
            <template v-if="(stats?.summary.processing_documents ?? 0) > 0">
              {{ stats!.summary.processing_documents }} 份处理中
            </template>
            <template v-else>全部就绪</template>
          </div>
        </div>
      </div>
    </div>
    <p class="stat-updated-at">统计更新：{{ formatTime(stats?.summary.computed_at) }}</p>

    <section class="section">
      <div class="section-head">
        <h2 class="section-title">最近知识库</h2>
        <router-link to="/knowledge-bases" class="view-all">查看全部 →</router-link>
      </div>
      <div v-if="loading" class="kb-grid">
        <div v-for="i in 4" :key="i" class="card kb-card"><div class="skeleton-block tall" /></div>
      </div>
      <div v-else-if="stats?.recent_knowledge_bases.length" class="kb-grid">
        <router-link
          v-for="kb in stats.recent_knowledge_bases"
          :key="kb.id"
          :to="`/knowledge-bases/${kb.id}`"
          class="card kb-card"
        >
          <div class="kb-card-head">
            <div class="kb-icon" :class="kbIconClass(kb.category)" aria-hidden="true">{{ kbIcon(kb.category) }}</div>
            <div class="kb-card-title-wrap">
              <div class="kb-card-title">{{ kb.name }}</div>
              <el-tooltip :content="kb.description" placement="top" :show-after="300">
                <div class="kb-card-desc">{{ kb.description }}</div>
              </el-tooltip>
            </div>
          </div>
          <div class="kb-card-stats">{{ kb.total_documents }} 文档 · {{ kb.retrievable_chunks }} 片段</div>
          <div class="kb-card-foot">
            <StatusBadge :status="kb.status" :label="statusLabel(kb.status)" />
            <span class="kb-updated">更新于 {{ formatTime(kb.updated_at) }}</span>
          </div>
        </router-link>
      </div>
      <div v-else class="card">
        <EmptyState
          icon="📚"
          title="还没有知识库"
          description="创建第一个知识库并上传文档，即可开始构建企业知识索引。"
          action-label="新建知识库"
          @action="kbDialogRef?.open()"
        />
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <h2 class="section-title">最近对话</h2>
        <router-link to="/chat" class="view-all">查看全部 →</router-link>
      </div>
      <div class="card table-card">
        <table v-if="stats?.recent_conversations.length" class="data-table">
          <thead>
            <tr>
              <th>问题</th>
              <th>使用知识库</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="conv in stats.recent_conversations" :key="conv.id">
              <td>
                <router-link :to="`/chat?conversation=${conv.id}`" class="conv-question">
                  <span class="q-icon" aria-hidden="true">💬</span>{{ conv.question }}
                </router-link>
              </td>
              <td>
                <span v-for="name in conv.kb_names" :key="name" class="kb-chip">{{ name }}</span>
              </td>
              <td class="muted">{{ formatTime(conv.updated_at) }}</td>
            </tr>
          </tbody>
        </table>
        <EmptyState
          v-else
          icon="💬"
          title="还没有对话记录"
          description="在 AI 问答中选择知识库并提问，回答将附带可溯源的引用来源。"
        />
      </div>
    </section>

    <KbDialog ref="kbDialogRef" @saved="load" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { statsApi, type DashboardStats } from '../api'
import { formatTime } from '../utils/format'
import StatusBadge from '../components/StatusBadge.vue'
import EmptyState from '../components/EmptyState.vue'
import KbDialog from '../components/KbDialog.vue'

const stats = ref<DashboardStats | null>(null)
const loading = ref(true)
const kbDialogRef = ref<InstanceType<typeof KbDialog>>()

function formatNumber(n?: number) {
  if (n === undefined || n === null) return '-'
  return n.toLocaleString('zh-CN')
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    READY: 'READY',
    UPDATING: 'UPDATING',
    PARTIAL: 'PARTIAL',
    EMPTY: 'EMPTY',
  }
  const extra: Record<string, string> = {
    UPDATING: '（有文档处理中）',
    PARTIAL: '（有文档失败）',
  }
  return (map[status] || status) + (extra[status] || '')
}

function kbIcon(category: string) {
  const map: Record<string, string> = {
    hr: '👥',
    finance: '¥',
    product: '📦',
    service: '🎧',
    procurement: '🛒',
    compliance: '🛡',
    general: '📘',
  }
  return map[category] || '📘'
}

function kbIconClass(category: string) {
  const map: Record<string, string> = {
    hr: 'kb-icon-blue',
    finance: 'kb-icon-indigo',
    product: 'kb-icon-cyan',
    service: 'kb-icon-indigo',
    procurement: 'kb-icon-amber',
    compliance: 'kb-icon-green',
    general: 'kb-icon-blue',
  }
  return map[category] || 'kb-icon-blue'
}

async function load() {
  loading.value = true
  try {
    stats.value = await statsApi.dashboard()
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.hero {
  margin-bottom: 20px;
}
.hero-title {
  font-size: 22px;
  font-weight: 800;
  margin: 0 0 4px;
}
.hero-sub {
  color: var(--text-secondary);
  margin: 0;
  font-size: 13px;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
}
.stat-icon {
  width: 46px;
  height: 46px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}
.stat-icon-blue { background: #eff6ff; }
.stat-icon-green { background: var(--green-bg); }
.stat-icon-indigo { background: var(--primary-light); }
.stat-icon-amber { background: var(--amber-bg); }
.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
}
.stat-value {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.3px;
}
.stat-value-sm {
  font-size: 15px;
}
.section {
  margin-top: 28px;
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.view-all {
  color: var(--primary);
  font-size: 13px;
  text-decoration: none;
  font-weight: 500;
}
.kb-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.kb-card {
  padding: 18px;
  text-decoration: none;
  color: var(--text);
  transition: box-shadow 0.15s, transform 0.15s;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.kb-card:hover {
  box-shadow: 0 6px 18px rgba(17, 24, 39, 0.07);
  transform: translateY(-1px);
}
.kb-card-head {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}
.kb-icon {
  width: 42px;
  height: 42px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  flex-shrink: 0;
}
.kb-icon-blue { background: #eff6ff; color: #2563eb; }
.kb-icon-indigo { background: var(--primary-light); color: var(--primary); }
.kb-icon-cyan { background: #ecfeff; color: #0891b2; }
.kb-icon-amber { background: var(--amber-bg); color: #d97706; }
.kb-icon-green { background: var(--green-bg); color: var(--green); }
.kb-card-title {
  font-weight: 700;
  font-size: 14px;
}
.kb-card-desc {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 3px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.kb-card-stats {
  font-size: 12px;
  color: var(--text-secondary);
}
.kb-card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
}
.kb-updated {
  font-size: 11px;
  color: var(--text-tertiary);
}
.table-card {
  padding: 6px 0;
}
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.data-table th {
  text-align: left;
  font-weight: 600;
  color: var(--text-tertiary);
  font-size: 12px;
  padding: 12px 20px;
  border-bottom: 1px solid var(--border);
}
.data-table td {
  padding: 13px 20px;
  border-bottom: 1px solid #f3f4f6;
}
.data-table tr:last-child td {
  border-bottom: none;
}
.conv-question {
  color: var(--text);
  text-decoration: none;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.conv-question:hover {
  color: var(--primary);
}
.q-icon {
  font-size: 13px;
}
.kb-chip {
  display: inline-block;
  background: #f3f4f6;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 2px 8px;
  font-size: 12px;
  margin-right: 6px;
  color: var(--text-secondary);
}
.muted {
  color: var(--text-tertiary);
}
.skeleton-block {
  height: 70px;
  border-radius: 8px;
  background: linear-gradient(90deg, #f3f4f6 25%, #e9eaec 50%, #f3f4f6 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
}
.skeleton-block.tall {
  height: 120px;
}
@keyframes shimmer {
  to { background-position: -200% 0; }
}
@media (max-width: 1279px) {
  .stats-grid, .kb-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 767px) {
  .stats-grid, .kb-grid { grid-template-columns: 1fr; }
}
</style>
