<template>
  <div v-if="loading" class="inspector-loading">加载中…</div>
  <div v-else-if="detail" class="inspector">
    <div class="inspector-head">
      <div class="doc-title-row">
        <span class="doc-big-icon" aria-hidden="true">📄</span>
        <div>
          <h2 class="doc-title">{{ detail.document?.title }}</h2>
          <StatusBadge
            :status="detail.lifecycle_status"
            :label="detail.lifecycle_status === 'CURRENT' ? '当前生效 · READY' : '历史版'"
          />
        </div>
      </div>
      <button class="close-btn" aria-label="关闭详情" @click="$emit('close')">✕</button>
    </div>
    <p class="doc-subtitle">{{ detail.document?.department || detail.document?.title }}</p>

    <div class="info-list">
      <div class="info-row"><span class="info-label">文档名称</span><span class="info-value">{{ detail.document?.title }}</span></div>
      <div class="info-row"><span class="info-label">制度版本</span><span class="info-value">{{ detail.version_label }}</span></div>
      <div class="info-row"><span class="info-label">文件版本</span><span class="info-value">{{ detail.file_version }}</span></div>
      <div class="info-row">
        <span class="info-label">当前状态</span>
        <span class="info-value"><StatusBadge :status="detail.processing_status" :label="processingLabel" /></span>
      </div>
      <div class="info-row"><span class="info-label">生效日期</span><span class="info-value">{{ formatDate(detail.effective_date) }}</span></div>
      <div class="info-row"><span class="info-label">文件类型</span><span class="info-value">{{ (detail.file_type || '').toUpperCase() }}</span></div>
      <div class="info-row"><span class="info-label">文件大小</span><span class="info-value">{{ formatBytes(detail.file_size) }}</span></div>
      <div v-if="detail.error_message" class="info-row error-row">
        <span class="info-label">失败原因</span><span class="info-value error-text">{{ detail.error_message }}</span>
      </div>
    </div>

    <div v-if="detail.parse_overview" class="parse-grid">
      <div class="parse-item">
        <div class="parse-value">{{ detail.parse_overview.child_chunks }}</div>
        <div class="parse-label">检索片段</div>
      </div>
      <div class="parse-item">
        <div class="parse-value">{{ detail.parse_overview.parent_chunks }}</div>
        <div class="parse-label">父级上下文</div>
      </div>
      <div class="parse-item">
        <div class="parse-value">{{ detail.chunk_preview?.total ?? 0 }}</div>
        <div class="parse-label">片段总数</div>
      </div>
      <div class="parse-item">
        <div class="parse-value">{{ (detail.file_type || '').toUpperCase() }}</div>
        <div class="parse-label">格式</div>
      </div>
    </div>

    <div v-if="detail.chunk_preview?.items?.length" class="chunk-section">
      <h3 class="sub-title">片段预览</h3>
      <div v-for="(c, i) in detail.chunk_preview.items" :key="i" class="chunk-card">
        <div class="chunk-head">
          <span class="chunk-path">{{ c.heading_path || '（无章节）' }}</span>
          <span class="chunk-idx">片段 #{{ c.chunk_index }}</span>
        </div>
        <p class="chunk-content">{{ c.content }}</p>
      </div>
    </div>

    <div class="version-section">
      <h3 class="sub-title">版本历史</h3>
      <div v-if="versions.length" class="version-list">
        <div v-for="v in versions" :key="v.id" class="version-row">
          <span class="v-label">{{ v.version_label }}</span>
          <span class="v-file">文件 {{ v.file_version }}</span>
          <StatusBadge
            :status="v.lifecycle_status"
            :label="v.lifecycle_status === 'CURRENT' ? '当前生效' : '历史版'"
          />
          <span class="v-date">{{ formatDate(v.effective_date) }}</span>
        </div>
      </div>
      <p v-else class="muted small">仅一个版本</p>
    </div>

    <div class="inspector-actions">
      <el-button @click="openOriginal">打开原文件</el-button>
      <el-button
        v-if="detail.processing_status === 'NEEDS_REINDEX' || detail.processing_status === 'FAILED'"
        type="warning"
        :loading="reindexing"
        @click="reindex"
      >
        重建索引
      </el-button>
      <el-button type="danger" plain @click="removeVersion">删除文档</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { docApi } from '../api'
import { formatDate, formatBytes } from '../utils/format'
import StatusBadge from './StatusBadge.vue'

const props = defineProps<{ documentId: number }>()
const emit = defineEmits<{ close: []; changed: [] }>()

const loading = ref(true)
const detail = ref<any>(null)
const versions = ref<any[]>([])
const reindexing = ref(false)

const processingLabel = computed(() => {
  const map: Record<string, string> = {
    READY: 'READY',
    UPLOADED: '已上传',
    PARSING: '解析中',
    CHUNKING: '切片中',
    INDEXING: '索引中',
    FAILED: '失败',
    NEEDS_REINDEX: '待重建索引',
  }
  return map[detail.value?.processing_status] || detail.value?.processing_status || ''
})

async function load() {
  loading.value = true
  try {
    detail.value = await docApi.version(props.documentId)
    const docDetail = await docApi.get(detail.value.document.id)
    versions.value = docDetail.versions || []
  } catch (err: any) {
    ElMessage.error(err.message || '加载文档详情失败')
  } finally {
    loading.value = false
  }
}

function openOriginal() {
  window.open(docApi.fileUrl(props.documentId), '_blank')
}

async function reindex() {
  reindexing.value = true
  try {
    await docApi.reindex(props.documentId)
    ElMessage.success('重建索引完成')
    await load()
    emit('changed')
  } catch (err: any) {
    ElMessage.error(err.message || '重建失败')
  } finally {
    reindexing.value = false
  }
}

async function removeVersion() {
  try {
    await ElMessageBox.confirm('确定删除该文档的所有版本与索引数据吗？此操作不可恢复。', '删除文档', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    // Note: document-level deletion endpoint shares doc detail API (DELETE /documents/{id})
    await docApi.remove?.(props.documentId)
    emit('changed')
    emit('close')
  } catch {
    /* cancelled */
  }
}

onMounted(load)
</script>

<style scoped>
.inspector { padding: 4px 2px; }
.inspector-loading { padding: 40px; text-align: center; color: var(--text-secondary); }
.inspector-head { display: flex; justify-content: space-between; align-items: flex-start; }
.doc-title-row { display: flex; gap: 12px; align-items: center; }
.doc-big-icon {
  width: 44px; height: 44px; border-radius: 11px;
  background: var(--primary-light); display: flex; align-items: center; justify-content: center;
  font-size: 20px;
}
.doc-title { font-size: 17px; font-weight: 800; margin: 0 0 4px; }
.close-btn {
  border: none; background: transparent; cursor: pointer;
  font-size: 15px; color: var(--text-tertiary); padding: 6px; border-radius: 6px;
}
.close-btn:hover { background: #f3f4f6; color: var(--text); }
.doc-subtitle { color: var(--text-secondary); font-size: 12px; margin: 8px 0 16px; }
.info-list { display: flex; flex-direction: column; }
.info-row {
  display: flex; justify-content: space-between; gap: 12px;
  padding: 9px 0; border-bottom: 1px solid #f5f6f8; font-size: 13px;
}
.info-label { color: var(--text-tertiary); flex-shrink: 0; }
.info-value { text-align: right; font-weight: 500; word-break: break-all; }
.error-row .error-text { color: var(--red); font-weight: 400; }
.parse-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 18px 0;
}
.parse-item {
  border: 1px solid var(--border); border-radius: 10px;
  padding: 12px 6px; text-align: center;
}
.parse-value { font-size: 17px; font-weight: 800; }
.parse-label { font-size: 11px; color: var(--text-tertiary); margin-top: 3px; }
.sub-title { font-size: 14px; font-weight: 700; margin: 18px 0 10px; }
.chunk-card {
  border: 1px solid var(--border); border-radius: 10px;
  padding: 12px 14px; margin-bottom: 10px;
}
.chunk-head { display: flex; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
.chunk-path { font-size: 12px; color: var(--primary); font-weight: 600; }
.chunk-idx { font-size: 11px; color: var(--text-tertiary); }
.chunk-content {
  font-size: 12.5px; color: var(--text-secondary); line-height: 1.65; margin: 0;
  display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden;
}
.version-list { display: flex; flex-direction: column; gap: 8px; }
.version-row {
  display: flex; align-items: center; gap: 10px;
  border: 1px solid var(--border); border-radius: 10px; padding: 9px 12px; font-size: 12.5px;
}
.v-label { font-weight: 700; }
.v-file { color: var(--text-secondary); }
.v-date { margin-left: auto; color: var(--text-tertiary); }
.inspector-actions {
  display: flex; gap: 10px; margin-top: 22px; padding-top: 16px;
  border-top: 1px solid var(--border);
}
.muted { color: var(--text-tertiary); }
.small { font-size: 12px; }
</style>
