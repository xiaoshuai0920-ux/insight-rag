<template>
  <div>
    <div class="hero">
      <h1 class="hero-title">知识库</h1>
      <p class="hero-sub">集中管理企业知识、文档与索引状态</p>
    </div>

    <div class="search-wrap">
      <span class="search-icon" aria-hidden="true">🔍</span>
      <input
        v-model="query"
        class="search-input"
        type="search"
        placeholder="搜索知识库名称或描述..."
        aria-label="搜索知识库"
        @input="debouncedLoad"
      />
    </div>

    <div v-if="loading" class="kb-grid">
      <div v-for="i in 6" :key="i" class="card kb-card"><div class="skeleton tall" /></div>
    </div>

    <div v-else-if="kbs.length" class="kb-grid">
      <div v-for="kb in kbs" :key="kb.id" class="card kb-card">
        <div class="kb-top">
          <div class="kb-icon" :class="iconClass(kb.category)" aria-hidden="true">{{ icon(kb.category) }}</div>
          <div class="kb-head-text">
            <router-link :to="`/knowledge-bases/${kb.id}`" class="kb-name">{{ kb.name }}</router-link>
            <el-tooltip :content="kb.description" placement="top" :show-after="300">
              <p class="kb-desc">{{ kb.description || '暂无描述' }}</p>
            </el-tooltip>
          </div>
          <el-dropdown trigger="click" @command="(cmd: string) => handleCommand(cmd, kb)">
            <button class="kb-menu" :aria-label="`${kb.name} 更多操作`" @click.stop>⋯</button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="edit">编辑</el-dropdown-item>
                <el-dropdown-item command="delete" divided style="color: var(--red)">删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <div class="kb-stats">{{ kb.total_documents }} 文档 · {{ kb.retrievable_chunks }} 片段</div>
        <div class="kb-foot">
          <StatusBadge
            :status="kb.status"
            :label="statusLabel(kb.status, kb)"
          />
          <span class="kb-updated">更新于 {{ formatTime(kb.updated_at) }}</span>
        </div>
      </div>
    </div>

    <div v-else class="card">
      <EmptyState
        :icon="query ? '🔍' : '📚'"
        :title="query ? '没有匹配的知识库' : '还没有知识库'"
        :description="query ? '换个关键词试试，或创建一个新的知识库。' : '新建知识库并上传 PDF / DOCX / Markdown / TXT 文档，即可开始构建知识索引。'"
        :action-label="query ? '' : '新建知识库'"
        @action="kbDialogRef?.open()"
      />
    </div>

    <p v-if="kbs.length" class="stat-updated-at">统计更新：{{ formatTime(new Date()) }}</p>
    <KbDialog ref="kbDialogRef" @saved="load" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { kbApi, type KnowledgeBase } from '../api'
import { formatTime } from '../utils/format'
import StatusBadge from '../components/StatusBadge.vue'
import EmptyState from '../components/EmptyState.vue'
import KbDialog from '../components/KbDialog.vue'

const kbs = ref<KnowledgeBase[]>([])
const loading = ref(true)
const query = ref('')
const kbDialogRef = ref<InstanceType<typeof KbDialog>>()
let debounceTimer: ReturnType<typeof setTimeout> | null = null

function statusLabel(status: string, kb: KnowledgeBase) {
  const base: Record<string, string> = {
    READY: 'READY',
    UPDATING: 'UPDATING',
    PARTIAL: 'PARTIAL',
    EMPTY: 'EMPTY',
  }
  const suffix: Record<string, string> = {
    UPDATING: `（${kb.processing_documents} 份处理中）`,
    PARTIAL: `（${kb.failed_documents} 份失败）`,
  }
  return (base[status] || status) + (suffix[status] || '')
}

function icon(category: string) {
  const map: Record<string, string> = {
    hr: '👥', finance: '¥', product: '📦', service: '🎧',
    procurement: '🛒', compliance: '🛡', general: '📘',
  }
  return map[category] || '📘'
}

function iconClass(category: string) {
  const map: Record<string, string> = {
    hr: 'icon-blue', finance: 'icon-indigo', product: 'icon-cyan', service: 'icon-indigo',
    procurement: 'icon-amber', compliance: 'icon-green', general: 'icon-blue',
  }
  return map[category] || 'icon-blue'
}

function debouncedLoad() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(load, 300)
}

async function load() {
  loading.value = true
  try {
    kbs.value = await kbApi.list(query.value)
  } catch (err: any) {
    ElMessage.error(err.message || '加载知识库失败')
  } finally {
    loading.value = false
  }
}

async function handleCommand(cmd: string, kb: KnowledgeBase) {
  if (cmd === 'edit') {
    editTarget.value = kb
    kbDialogRef.value?.open()
    // KbDialog watches props.kb; re-open with edit target
  } else if (cmd === 'delete') {
    try {
      await ElMessageBox.confirm(
        `确定删除「${kb.name}」吗？该操作将同时删除其中的所有文档与索引，不可恢复。`,
        '删除知识库',
        { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
      )
      await kbApi.remove(kb.id)
      ElMessage.success('知识库已删除')
      load()
    } catch {
      /* cancelled */
    }
  }
}

const editTarget = ref<KnowledgeBase | null>(null)

onMounted(load)
</script>

<style scoped>
.hero { margin-bottom: 18px; }
.hero-title { font-size: 22px; font-weight: 800; margin: 0 0 4px; }
.hero-sub { color: var(--text-secondary); margin: 0; font-size: 13px; }
.search-wrap {
  display: flex;
  align-items: center;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0 14px;
  margin-bottom: 20px;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.search-wrap:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}
.search-icon { color: var(--text-tertiary); margin-right: 8px; }
.search-input {
  flex: 1;
  border: none;
  outline: none;
  padding: 12px 0;
  font-size: 14px;
  background: transparent;
}
.kb-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.kb-card {
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: box-shadow 0.15s;
}
.kb-card:hover { box-shadow: 0 6px 18px rgba(17, 24, 39, 0.07); }
.kb-top { display: flex; gap: 12px; align-items: flex-start; }
.kb-icon {
  width: 44px; height: 44px; border-radius: 11px;
  display: flex; align-items: center; justify-content: center;
  font-size: 19px; font-weight: 700; flex-shrink: 0;
}
.icon-blue { background: #eff6ff; color: #2563eb; }
.icon-indigo { background: var(--primary-light); color: var(--primary); }
.icon-cyan { background: #ecfeff; color: #0891b2; }
.icon-amber { background: var(--amber-bg); color: #d97706; }
.icon-green { background: var(--green-bg); color: var(--green); }
.kb-head-text { flex: 1; min-width: 0; }
.kb-name {
  font-weight: 700; font-size: 14px; color: var(--text);
  text-decoration: none;
}
.kb-name:hover { color: var(--primary); }
.kb-desc {
  font-size: 12px; color: var(--text-secondary); margin: 3px 0 0;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.kb-menu {
  border: none; background: transparent; cursor: pointer;
  font-size: 16px; color: var(--text-tertiary);
  padding: 2px 8px; border-radius: 6px;
  visibility: visible;
}
.kb-card:hover .kb-menu { color: var(--text-secondary); }
.kb-menu:hover { background: #f3f4f6; }
.kb-stats { font-size: 12px; color: var(--text-secondary); }
.kb-foot { display: flex; align-items: center; justify-content: space-between; margin-top: auto; }
.kb-updated { font-size: 11px; color: var(--text-tertiary); }
.skeleton {
  height: 150px;
  border-radius: 8px;
  background: linear-gradient(90deg, #f3f4f6 25%, #e9eaec 50%, #f3f4f6 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
}
@keyframes shimmer { to { background-position: -200% 0; } }
@media (max-width: 1279px) { .kb-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 767px) { .kb-grid { grid-template-columns: 1fr; } }
</style>
