<template>
  <el-drawer
    :model-value="true"
    direction="rtl"
    size="440px"
    :with-header="false"
    :append-to-body="true"
    @close="$emit('close')"
  >
    <div v-if="loading" class="source-loading">加载中…</div>
    <div v-else-if="source" class="source-panel">
      <div class="sp-head">
        <h2 class="sp-title">来源</h2>
        <button class="close-btn" aria-label="关闭来源面板" @click="$emit('close')">✕</button>
      </div>

      <div class="sp-doc-head">
        <span class="sp-doc-icon" aria-hidden="true">{{ fileIcon }}</span>
        <div class="sp-doc-meta">
          <div class="sp-doc-title">{{ source.document_title }}</div>
          <div class="sp-badges">
            <StatusBadge
              :status="source.lifecycle_status || 'CURRENT'"
              :label="source.lifecycle_status === 'HISTORICAL' ? '历史版' : '当前生效'"
            />
            <span class="meta-chip">制度版本 {{ source.version_label }}</span>
            <span v-if="source.file_version" class="meta-chip">文件版本 {{ source.file_version }}</span>
          </div>
        </div>
        <button class="open-original" aria-label="打开原文件" title="打开原文件" @click="openOriginal">↗</button>
      </div>

      <div class="sp-info-card">
        <div class="sp-info-row"><span>引用位置</span><b>{{ source.heading_path || '-' }}</b></div>
        <div class="sp-info-row"><span>页码</span><b>{{ source.page_number ? `第 ${source.page_number} 页` : '-' }}</b></div>
        <div class="sp-info-row"><span>生效日期</span><b>{{ formatDate(source.effective_date) }}</b></div>
      </div>

      <h3 class="sp-sub">文档信息</h3>
      <div class="sp-info-card" v-if="docDetail">
        <div class="sp-info-row"><span>文件类型</span><b>{{ (docDetail.file_type || '').toUpperCase() }}</b></div>
        <div class="sp-info-row"><span>所属知识库</span><b>{{ source.kb_name || '-' }}</b></div>
        <div class="sp-info-row"><span>更新时间</span><b>{{ formatTime(docDetail.updated_at) }}</b></div>
      </div>

      <h3 class="sp-sub">原文内容</h3>
      <div class="sp-content-card" ref="contentRef">
        <template v-for="(block, i) in contentBlocks" :key="i">
          <p
            v-if="block.type === 'p'"
            :class="{ 'quote-highlight': block.highlight }"
          >{{ block.text }}</p>
          <h4 v-else class="sp-heading">{{ block.text }}</h4>
        </template>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { docApi } from '../api'
import { formatDate, formatTime } from '../utils/format'
import StatusBadge from './StatusBadge.vue'

const props = defineProps<{
  citation: {
    document_id: number
    document_version_id: number
    chunk_id: number | null
    document_title: string
    version_label: string
    file_version?: string
    heading_path?: string
    page_number?: number | null
    effective_date?: string | null
    quote_text?: string
    kb_name?: string
    kb_category?: string
    lifecycle_status?: string
  }
}>()

defineEmits<{ close: [] }>()

const loading = ref(true)
const source = ref<any>(null)
const docDetail = ref<any>(null)
const contentRef = ref<HTMLElement>()

const fileIcon = computed(() => {
  const map: Record<string, string> = { pdf: '📕', docx: '📘', md: '📗', txt: '📄' }
  return map[(docDetail.value?.file_type || '').toLowerCase()] || '📄'
})

interface Block {
  type: 'p' | 'h'
  text: string
  highlight: boolean
}

const contentBlocks = computed<Block[]>(() => {
  const raw = source.value?.full_context || source.value?.quote_text || ''
  const quote = (props.citation.quote_text || '').slice(0, 80)
  const blocks: Block[] = []
  for (const line of raw.split('\n')) {
    const t = line.trim()
    if (!t) continue
    const isHeading = /^(第[一二三四五六七八九十百\d]+[章节篇条]|[一二三四五六七八九十]+[、.．]|\d+(\.\d+)*)/.test(t) && t.length < 40
    blocks.push({
      type: isHeading ? 'h' : 'p',
      text: t,
      highlight: !!quote && t.includes(quote.slice(0, 30)) === false && t.includes(quote.slice(0, 20)),
    })
  }
  // highlight the paragraph that contains the quote start
  if (quote) {
    const key = quote.replace(/\s+/g, '').slice(0, 30)
    for (const b of blocks) {
      const flat = b.text.replace(/\s+/g, '')
      if (flat.includes(key.slice(0, 20))) {
        b.highlight = true
        break
      }
    }
  }
  return blocks
})

function openOriginal() {
  window.open(docApi.fileUrl(props.citation.document_version_id), '_blank')
}

onMounted(async () => {
  try {
    const version = await docApi.version(props.citation.document_version_id)
    docDetail.value = version
    // build full context from parent chunk (or child fallback)
    let full = props.citation.quote_text || ''
    if (props.citation.chunk_id) {
      try {
        const chunks = await docApi.chunks(props.citation.document_version_id, 'PARENT')
        const childChunks = await docApi.chunks(props.citation.document_version_id, 'CHILD')
        const child = childChunks.find((c: any) => c.id === props.citation.chunk_id)
        if (child?.parent_id) {
          const parent = chunks.find((c: any) => c.id === child.parent_id)
          if (parent) full = parent.content
        } else if (child) {
          full = child.content
        }
      } catch {
        /* keep quote */
      }
    }
    source.value = {
      ...props.citation,
      full_context: full,
    }
  } catch {
    source.value = { ...props.citation, full_context: props.citation.quote_text || '' }
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.source-loading { padding: 40px; text-align: center; color: var(--text-secondary); }
.source-panel { padding: 4px 2px; }
.sp-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.sp-title { font-size: 16px; font-weight: 800; margin: 0; }
.close-btn {
  border: none; background: transparent; cursor: pointer;
  font-size: 15px; color: var(--text-tertiary); padding: 6px; border-radius: 6px;
}
.close-btn:hover { background: #f3f4f6; }
.sp-doc-head { display: flex; gap: 12px; align-items: flex-start; }
.sp-doc-icon {
  width: 42px; height: 42px; border-radius: 10px; background: var(--red-bg);
  display: flex; align-items: center; justify-content: center; font-size: 19px; flex-shrink: 0;
}
.sp-doc-meta { flex: 1; min-width: 0; }
.sp-doc-title { font-weight: 800; font-size: 15px; }
.sp-badges { display: flex; gap: 6px; margin-top: 6px; flex-wrap: wrap; align-items: center; }
.meta-chip {
  font-size: 11px; background: #f3f4f6; border: 1px solid var(--border);
  border-radius: 5px; padding: 2px 7px; color: var(--text-secondary);
}
.open-original {
  border: 1px solid var(--border); background: #fff; border-radius: 8px;
  width: 30px; height: 30px; cursor: pointer; color: var(--text-secondary);
}
.open-original:hover { border-color: var(--primary); color: var(--primary); }
.sp-sub { font-size: 13px; font-weight: 700; margin: 20px 0 8px; }
.sp-info-card {
  border: 1px solid var(--border); border-radius: 10px; padding: 4px 14px;
}
.sp-info-row {
  display: flex; justify-content: space-between; padding: 9px 0; font-size: 13px;
  border-bottom: 1px solid #f5f6f8;
}
.sp-info-row:last-child { border-bottom: none; }
.sp-info-row span { color: var(--text-tertiary); }
.sp-info-row b { font-weight: 600; text-align: right; }
.sp-content-card {
  border: 1px solid var(--border); border-radius: 10px;
  padding: 16px 18px; max-height: 420px; overflow-y: auto;
}
.sp-content-card p { font-size: 13.5px; line-height: 1.8; margin: 0 0 10px; color: var(--text); }
.sp-heading { font-size: 13.5px; font-weight: 700; margin: 12px 0 6px; }
</style>
