<template>
  <div>
    <div class="detail-head">
      <router-link to="/knowledge-bases" class="back-link">← 返回工作台</router-link>
      <div class="head-row">
        <div>
          <h1 class="kb-title">{{ kb?.name || '…' }}</h1>
          <p class="kb-desc">{{ kb?.description }}</p>
        </div>
      </div>
      <div class="detail-stats" v-if="kb">
        <div class="dstat">
          <span class="dstat-icon" aria-hidden="true">📄</span>
          <div><div class="dstat-value">{{ kb.total_documents }}</div><div class="dstat-label">个文档</div></div>
        </div>
        <div class="dstat">
          <span class="dstat-icon" aria-hidden="true">🗂</span>
          <div><div class="dstat-value">{{ kb.retrievable_chunks }}</div><div class="dstat-label">个可检索片段</div></div>
        </div>
        <div class="dstat">
          <StatusBadge v-if="kb.status" :status="kb.status" :label="kbStatusDetail" />
        </div>
      </div>
      <p class="stat-updated-at">统计更新：{{ formatTime(new Date()) }}</p>
    </div>

    <div class="tabs-bar" role="tablist">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'documents' }"
        role="tab"
        :aria-selected="activeTab === 'documents'"
        @click="activeTab = 'documents'"
      >
        文档
      </button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'settings' }"
        role="tab"
        :aria-selected="activeTab === 'settings'"
        @click="activeTab = 'settings'"
      >
        知识库设置
      </button>
    </div>

    <!-- Documents tab -->
    <div v-show="activeTab === 'documents'" class="tab-body">
      <div class="doc-toolbar">
        <div class="search-wrap">
          <span class="search-icon" aria-hidden="true">🔍</span>
          <input
            v-model="docQuery"
            class="search-input"
            type="search"
            placeholder="搜索文档名称、关键词..."
            aria-label="搜索文档"
            @input="debouncedLoadDocs"
          />
        </div>
        <button class="btn-primary" @click="uploadTrigger">
          <span aria-hidden="true">＋</span> 上传文档
        </button>
        <input
          ref="fileInputRef"
          type="file"
          accept=".pdf,.docx,.doc,.md,.markdown,.txt"
          style="display: none"
          @change="handleFileChange"
        />
      </div>

      <div v-if="docsLoading" class="card"><div class="skeleton tall" /></div>
      <div v-else-if="docs.length" class="card table-card">
        <table class="data-table">
          <thead>
            <tr>
              <th>文档名称</th>
              <th>制度版本</th>
              <th>文件版本</th>
              <th>生效日期</th>
              <th>状态</th>
              <th>更新时间</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="doc in docs"
              :key="doc.id"
              :class="{ selected: selectedDocId === doc.id }"
              @click="openInspector(doc)"
            >
              <td>
                <span class="doc-name">
                  <span class="doc-file-icon" aria-hidden="true">{{ fileIcon(doc.current_version?.file_type) }}</span>
                  {{ doc.title }}
                </span>
              </td>
              <td>{{ doc.current_version?.version_label || '-' }}</td>
              <td>{{ doc.current_version?.file_version || '-' }}</td>
              <td>{{ formatDate(doc.current_version?.effective_date) }}</td>
              <td>
                <StatusBadge
                  v-if="doc.current_version"
                  :status="doc.current_version.processing_status"
                  :label="processingLabel(doc.current_version.processing_status)"
                />
                <span v-else>-</span>
              </td>
              <td class="muted" :title="doc.updated_at || ''">{{ formatTime(doc.updated_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="card">
        <EmptyState
          icon="📁"
          title="这个知识库还是空的"
          description="上传 PDF、DOCX、Markdown 或 TXT，即可开始构建知识索引。"
          action-label="上传第一份文档"
          @action="uploadTrigger"
        />
      </div>
    </div>

    <!-- KB settings tab -->
    <div v-show="activeTab === 'settings'" class="tab-body">
      <div class="card settings-card">
        <h3 class="card-title">基本信息</h3>
        <KbFormInline :kb="kb" @saved="reloadAll" />
      </div>
      <div class="card settings-card">
        <h3 class="card-title">索引重建</h3>
        <p class="card-hint">
          当 Embedding 模型更换后，此知识库的文档会标记为 NEEDS_REINDEX；可在设置页统一执行「更换并重建索引」，或在文档详情中单独重建。
        </p>
      </div>
    </div>

    <!-- Upload progress dialog -->
    <el-dialog v-model="uploading" title="正在上传文档" width="380px" :close-on-click-modal="false" :show-close="false">
      <div class="upload-progress">
        <el-progress :percentage="uploadProgress" :stroke-width="10" />
        <p class="muted small">{{ uploadFileName }} — 上传后系统将依次解析、切片并建立索引</p>
      </div>
    </el-dialog>

    <!-- Document Inspector drawer -->
    <el-drawer
      v-model="inspectorVisible"
      direction="rtl"
      size="440px"
      :with-header="false"
      :append-to-body="true"
      class="inspector-drawer"
    >
      <DocumentInspector
        v-if="inspectorDocId"
        :document-id="inspectorDocId"
        @close="inspectorVisible = false"
        @changed="loadDocs"
      />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { kbApi, docApi, type KnowledgeBase, type KbDocument } from '../api'
import { formatDate, formatTime } from '../utils/format'
import StatusBadge from '../components/StatusBadge.vue'
import EmptyState from '../components/EmptyState.vue'
import DocumentInspector from '../components/DocumentInspector.vue'
import KbFormInline from '../components/KbFormInline.vue'

const route = useRoute()
const kbId = Number(route.params.id)

const kb = ref<KnowledgeBase | null>(null)
const docs = ref<KbDocument[]>([])
const loading = ref(true)
const docsLoading = ref(false)
const docQuery = ref('')
const activeTab = ref<'documents' | 'settings'>('documents')
const fileInputRef = ref<HTMLInputElement>()
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadFileName = ref('')

const inspectorVisible = ref(false)
const inspectorDocId = ref<number | null>(null)
const selectedDocId = ref<number | null>(null)

const kbStatusDetail = computed(() => {
  if (!kb.value) return ''
  const map: Record<string, string> = {
    READY: 'READY',
    UPDATING: `UPDATING（${kb.value.processing_documents} 份处理中）`,
    PARTIAL: `PARTIAL（${kb.value.failed_documents} 份失败）`,
    EMPTY: 'EMPTY',
  }
  return map[kb.value.status] || kb.value.status
})

function processingLabel(status: string) {
  const map: Record<string, string> = {
    READY: 'READY',
    UPLOADED: '已上传',
    PARSING: '解析中',
    CHUNKING: '切片中',
    INDEXING: '索引中',
    FAILED: '失败',
    NEEDS_REINDEX: '待重建索引',
  }
  return map[status] || status
}

function fileIcon(type?: string) {
  const map: Record<string, string> = { pdf: '📕', docx: '📘', doc: '📘', md: '📗', markdown: '📗', txt: '📄' }
  return map[(type || '').toLowerCase()] || '📄'
}

function debouncedLoadDocs() {
  setTimeout(loadDocs, 250)
}

async function loadKb() {
  kb.value = await kbApi.get(kbId)
}

async function loadDocs() {
  docsLoading.value = true
  try {
    docs.value = await kbApi.documents(kbId, docQuery.value)
  } finally {
    docsLoading.value = false
  }
}

async function reloadAll() {
  await Promise.all([loadKb(), loadDocs()])
}

function uploadTrigger() {
  fileInputRef.value?.click()
}

async function handleFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploading.value = true
  uploadProgress.value = 0
  uploadFileName.value = file.name
  try {
    await docApi.upload(kbId, file, (pct) => (uploadProgress.value = pct))
    ElMessage.success(`${file.name} 上传成功，正在处理`)
    await loadDocs()
    startStatusPolling()
  } catch (err: any) {
    ElMessage.error(err.message || '上传失败')
  } finally {
    uploading.value = false
    input.value = ''
  }
}

let pollTimer: ReturnType<typeof setInterval> | null = null
function startStatusPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    if (!kb.value) return
    const fresh = await kbApi.get(kbId)
    kb.value = fresh
    await loadDocs()
    if (fresh.status === 'READY' || fresh.status === 'PARTIAL') {
      if (pollTimer) clearInterval(pollTimer)
      pollTimer = null
    }
  }, 4000)
  setTimeout(() => {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }, 120000)
}

function openInspector(doc: KbDocument) {
  selectedDocId.value = doc.id
  inspectorDocId.value = doc.id
  inspectorVisible.value = true
}

onMounted(async () => {
  loading.value = true
  try {
    await reloadAll()
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.back-link {
  color: var(--primary);
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
}
.head-row { display: flex; align-items: flex-start; justify-content: space-between; margin-top: 10px; }
.kb-title { font-size: 22px; font-weight: 800; margin: 0 0 4px; }
.kb-desc { color: var(--text-secondary); margin: 0; font-size: 13px; }
.detail-stats { display: flex; gap: 14px; margin-top: 16px; align-items: stretch; }
.dstat {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: 14px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 130px;
}
.dstat-icon {
  width: 38px; height: 38px; border-radius: 10px;
  background: var(--primary-light); color: var(--primary);
  display: flex; align-items: center; justify-content: center; font-size: 17px;
}
.dstat-value { font-size: 19px; font-weight: 800; }
.dstat-label { font-size: 11px; color: var(--text-tertiary); }
.tabs-bar {
  display: flex; gap: 4px; margin: 22px 0 16px;
  border-bottom: 1px solid var(--border);
}
.tab-btn {
  border: none; background: transparent; cursor: pointer;
  font-size: 14px; padding: 10px 16px; color: var(--text-secondary);
  border-bottom: 2px solid transparent; margin-bottom: -1px;
  font-weight: 500;
}
.tab-btn:hover { color: var(--text); }
.tab-btn.active { color: var(--primary); border-bottom-color: var(--primary); font-weight: 700; }
.doc-toolbar { display: flex; gap: 12px; margin-bottom: 16px; }
.search-wrap {
  flex: 1; display: flex; align-items: center;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 0 14px;
}
.search-wrap:focus-within { border-color: var(--primary); }
.search-icon { color: var(--text-tertiary); margin-right: 8px; }
.search-input { flex: 1; border: none; outline: none; padding: 11px 0; font-size: 14px; background: transparent; }
.table-card { padding: 6px 0; overflow: visible; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th {
  text-align: left; font-weight: 600; color: var(--text-tertiary);
  font-size: 12px; padding: 12px 18px; border-bottom: 1px solid var(--border);
}
.data-table td { padding: 13px 18px; border-bottom: 1px solid #f3f4f6; cursor: pointer; }
.data-table tr:last-child td { border-bottom: none; }
.data-table tbody tr:hover { background: #fafafa; }
.data-table tbody tr.selected { background: var(--primary-light); }
.doc-name { display: inline-flex; align-items: center; gap: 9px; font-weight: 500; }
.doc-file-icon { font-size: 15px; }
.muted { color: var(--text-tertiary); }
.settings-card { padding: 22px 24px; margin-bottom: 16px; }
.card-title { margin: 0 0 10px; font-size: 15px; }
.card-hint { color: var(--text-secondary); font-size: 13px; line-height: 1.7; margin: 0; }
.upload-progress { padding: 8px 0; }
.small { font-size: 12px; }
.skeleton {
  height: 160px; border-radius: 8px;
  background: linear-gradient(90deg, #f3f4f6 25%, #e9eaec 50%, #f3f4f6 75%);
  background-size: 200% 100%; animation: shimmer 1.4s infinite; margin: 8px;
}
@keyframes shimmer { to { background-position: -200% 0; } }
</style>
