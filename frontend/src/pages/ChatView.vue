<template>
  <div class="chat-page">
    <!-- Conversation list -->
    <aside class="conv-list" aria-label="对话记录">
      <div class="conv-head">
        <span class="conv-title">对话记录</span>
        <button class="new-conv-btn" aria-label="新建对话" title="新建对话" @click="newConversation">＋</button>
      </div>
      <div v-if="convLoading" class="conv-empty">加载中…</div>
      <div v-else-if="conversations.length" class="conv-items">
        <div
          v-for="c in conversations"
          :key="c.id"
          class="conv-item"
          :class="{ active: currentConvId === c.id }"
          @click="openConversation(c.id)"
        >
          <div class="conv-item-title">{{ c.title }}</div>
          <div class="conv-item-time">{{ formatTime(c.updated_at) }}</div>
        </div>
      </div>
      <div v-else class="conv-empty">暂无对话，发送第一条消息开始</div>
    </aside>

    <!-- Chat area -->
    <div class="chat-main">
      <div class="scope-bar">
        <span class="scope-label">知识库范围：</span>
        <div class="scope-chips">
          <span v-for="kb in selectedKbs" :key="kb.id" class="scope-chip">
            <span aria-hidden="true">{{ kbIcon(kb.category) }}</span> {{ kb.name }}
            <button class="chip-x" :aria-label="`移除 ${kb.name}`" @click="removeKb(kb.id)">✕</button>
          </span>
          <el-popover :width="300" trigger="click">
            <template #reference>
              <button class="add-kb-btn">＋ 选择知识库</button>
            </template>
            <div class="kb-picker">
              <div
                v-for="kb in availableKbs"
                :key="kb.id"
                class="kb-picker-item"
                :class="{ disabled: selectedKbs.length >= 5 && !isSelected(kb.id) }"
                @click="addKb(kb)"
              >
                <span aria-hidden="true">{{ kbIcon(kb.category) }}</span>
                <span class="picker-name">{{ kb.name }}</span>
                <span class="picker-status">{{ kb.status }}</span>
              </div>
              <p v-if="!availableKbs.length" class="picker-empty">没有更多可选知识库</p>
              <p class="picker-hint">最多同时选择 5 个知识库</p>
            </div>
          </el-popover>
        </div>
        <button
          v-if="selectedKbs.length"
          class="all-kb-btn"
          @click="selectedKbIds = []; loadMessages()"
        >
          ☰ 全部知识库
        </button>
        <el-dropdown v-if="!selectedKbs.length" trigger="click">
          <span class="all-kb-indicator">☰ 全部知识库 ▾</span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled>当前检索全部知识库</el-dropdown-item>
              <el-dropdown-item @click="scopePopoverFocus">点击上方 ＋ 选择指定知识库</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>

      <div ref="messagesRef" class="messages-area">
        <template v-if="messages.length">
          <div v-for="(m, idx) in messages" :key="idx" class="msg-row" :class="m.role === 'USER' ? 'user' : 'assistant'">
            <!-- user bubble -->
            <template v-if="m.role === 'USER'">
              <div class="msg-bubble user-bubble">{{ m.content }}</div>
              <div class="msg-avatar user-avatar-sm" aria-hidden="true">👤</div>
            </template>

            <!-- assistant message -->
            <template v-else>
              <div class="msg-avatar ai-avatar" aria-hidden="true">▶</div>
              <div class="msg-body">
                <!-- evidence banner -->
                <div v-if="m.evidence_status" class="evidence-banner" :class="evidenceClass(m.evidence_status)">
                  <span class="ev-icon" aria-hidden="true">{{ evidenceIcon(m.evidence_status) }}</span>
                  <div class="ev-text">
                    <b>{{ evidenceLabel(m.evidence_status) }}</b>
                    <span class="ev-meta">
                      检索范围：{{ scopeNoteOf(m) }} · 引用：{{ (m.citations || []).length }} 个片段
                      <template v-if="m.retrieval_meta?.total_latency_ms">
                        · 检索耗时 {{ Math.round(m.retrieval_meta.total_latency_ms) }} ms
                      </template>
                    </span>
                  </div>
                  <span class="ev-time">{{ m.timeText }}</span>
                </div>

                <div v-if="m.streaming && !m.content" class="typing-row">
                  <span class="spinner sm"></span>
                  <span class="typing-text">{{ m.stageText || '正在检索知识…' }}</span>
                </div>

                <!-- markdown answer -->
                <div v-else class="md-body msg-answer" v-html="renderMarkdown(m.content)"></div>

                <!-- retrieval process (collapsed by default) -->
                <details v-if="m.retrieval_meta && !m.streaming" class="retrieval-details">
                  <summary>查看检索过程</summary>
                  <div class="rp-grid">
                    <div class="rp-item"><span class="rp-k">检索范围</span><span class="rp-v">{{ scopeNoteOf(m) }}</span></div>
                    <div class="rp-item"><span class="rp-k">策略</span><span class="rp-v">{{ strategyLabel(m.retrieval_meta?.strategy) }}</span></div>
                    <div class="rp-item"><span class="rp-k">召回片段</span><span class="rp-v">{{ m.retrieval_meta?.hit_count ?? '-' }}</span></div>
                    <div class="rp-item"><span class="rp-k">总检索耗时</span><span class="rp-v">{{ Math.round(m.retrieval_meta?.total_latency_ms || 0) }} ms</span></div>
                  </div>
                  <div v-if="m.retrieval_meta?.stages?.length" class="rp-stages">
                    <span v-for="s in m.retrieval_meta.stages" :key="s.stage" class="rp-stage-chip">
                      {{ s.label }} {{ s.latency_ms }}ms
                    </span>
                  </div>
                  <p v-if="m.retrieval_meta?.reranker_used" class="rp-note">✓ Reranker 已参与重排</p>
                </details>

                <!-- citations -->
                <div v-if="(m.citations || []).length && !m.streaming" class="citations-card">
                  <div class="cit-head">
                    <span class="cit-title">引用来源（{{ m.citations.length }}）</span>
                    <button v-if="m.citations.length > 2" class="cit-all" @click="expandCitations[idx] = !expandCitations[idx]">
                      {{ expandCitations[idx] ? '收起' : '查看全部来源 →' }}
                    </button>
                  </div>
                  <div
                    v-for="c in visibleCitations(m, idx)"
                    :key="c.citation_index"
                    class="citation-row"
                    role="button"
                    tabindex="0"
                    @click="openSource(c)"
                    @keydown.enter="openSource(c)"
                  >
                    <span class="cit-idx">[{{ c.citation_index }}]</span>
                    <div class="cit-main">
                      <div class="cit-doc-title">
                        {{ c.document_title }}
                        <StatusBadge
                          :status="c.lifecycle_status || 'CURRENT'"
                          :label="c.lifecycle_status === 'HISTORICAL' ? '历史版' : '当前生效'"
                        />
                        <span class="meta-chip">{{ c.version_label }}</span>
                      </div>
                      <div class="cit-path">{{ c.heading_path }}<template v-if="c.page_number"> — 第 {{ c.page_number }} 页</template></div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </template>

        <div v-else-if="!convLoading" class="chat-empty">
          <div class="chat-empty-icon" aria-hidden="true">▶</div>
          <h2>开始新的对话</h2>
          <p>选择知识库范围，输入问题。回答将附带可点击溯源的引用来源。</p>
          <div class="suggest-list">
            <button v-for="q in suggestions" :key="q" class="suggest-chip" @click="input = q">{{ q }}</button>
          </div>
        </div>
      </div>

      <div class="input-bar">
        <div v-if="streamError" class="stream-error" role="alert">
          <span>⚠ {{ streamError }}</span>
          <button class="retry-btn" @click="retryLast">重试</button>
        </div>
        <div class="input-row">
          <button class="attach-btn" aria-label="附件（即将支持）" title="附件（即将支持）" disabled>📎</button>
          <textarea
            ref="inputRef"
            v-model="input"
            class="chat-input"
            rows="1"
            placeholder="请输入您的问题，支持 Shift + Enter 换行"
            :disabled="streaming"
            @keydown.enter.exact.prevent="sendMessage"
            @input="autoGrow"
          ></textarea>
          <button class="send-btn" aria-label="发送" :disabled="streaming || !input.trim()" @click="sendMessage">
            <span v-if="streaming" class="spinner sm dark"></span>
            <span v-else aria-hidden="true">➤</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Source panel -->
    <SourcePanel v-if="sourceCitation" :citation="sourceCitation" @close="sourceCitation = null" />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import markdownit from 'markdown-it'
import { convApi, kbApi, type KnowledgeBase } from '../api'
import { streamSse } from '../api/client'
import { formatTime } from '../utils/format'
import StatusBadge from '../components/StatusBadge.vue'
import SourcePanel from '../components/SourcePanel.vue'

const md = markdownit({ breaks: true, linkify: true })

const route = useRoute()
const conversations = ref<{ id: number; title: string; updated_at: string | null }[]>([])
const convLoading = ref(true)
const currentConvId = ref<number | null>(null)
const allKbs = ref<KnowledgeBase[]>([])
const selectedKbIds = ref<number[]>([])
const messages = ref<any[]>([])
const input = ref('')
const streaming = ref(false)
const streamError = ref('')
const expandCitations = ref<Record<number, boolean>>({})
const sourceCitation = ref<any>(null)
const messagesRef = ref<HTMLElement>()
const inputRef = ref<HTMLTextAreaElement>()
let lastQuestion = ''
let currentController: AbortController | null = null

const suggestions = [
  '成都出差住宿标准是多少？',
  '年假可以休几天？',
  '报销需要哪些材料？',
  '员工入职流程是什么？',
]

const selectedKbs = computed(() => allKbs.value.filter((k) => selectedKbIds.value.includes(k.id)))
const availableKbs = computed(() => allKbs.value.filter((k) => !selectedKbIds.value.includes(k.id)))

function kbIcon(category: string) {
  const map: Record<string, string> = {
    hr: '👥', finance: '¥', product: '📦', service: '🎧',
    procurement: '🛒', compliance: '🛡', general: '📘',
  }
  return map[category] || '📘'
}

function isSelected(id: number) {
  return selectedKbIds.value.includes(id)
}

function addKb(kb: KnowledgeBase) {
  if (isSelected(kb.id)) return
  if (selectedKbIds.value.length >= 5) {
    ElMessage.warning('最多同时选择 5 个知识库')
    return
  }
  selectedKbIds.value.push(kb.id)
}

function removeKb(id: number) {
  selectedKbIds.value = selectedKbIds.value.filter((i) => i !== id)
}

function scopePopoverFocus() {
  /* helper for the empty-scope dropdown */
}

function strategyLabel(s?: string) {
  const map: Record<string, string> = {
    dense: 'Dense 向量检索',
    bm25: 'BM25 关键词检索',
    hybrid: 'Hybrid（Dense + BM25 + RRF）',
    hybrid_rerank: 'Hybrid + Reranker',
  }
  return map[s || ''] || s || '-'
}

function scopeNoteOf(m: any) {
  const names = m.retrieval_meta?.kb_names
  if (names?.length) return names.join('、')
  return m.retrieval_meta?.scope_note === '所选知识库' ? '所选知识库' : '全部知识库'
}

function evidenceLabel(s: string) {
  const map: Record<string, string> = {
    SUFFICIENT: '已检索到相关资料',
    INSUFFICIENT: '相关资料不足',
    CONFLICTING: '发现来源信息不一致',
  }
  return map[s] || s
}

function evidenceIcon(s: string) {
  return s === 'SUFFICIENT' ? '✔' : s === 'CONFLICTING' ? '⚠' : 'ℹ'
}

function evidenceClass(s: string) {
  return {
    'ev-ok': s === 'SUFFICIENT',
    'ev-warn': s === 'INSUFFICIENT',
    'ev-conflict': s === 'CONFLICTING',
  }
}

function visibleCitations(m: any, idx: number) {
  const list = m.citations || []
  return expandCitations.value[idx] ? list : list.slice(0, 2)
}

function renderMarkdown(content: string) {
  if (!content) return ''
  // turn [1] into clickable chips
  const html = md.render(content)
  return html.replace(/\[(\d{1,2})\]/g, (match, num) => {
    return `<button class="cite-chip" data-cite="${num}">${num}</button>`
  })
}

function openSource(c: any) {
  sourceCitation.value = c
}

async function loadConversations() {
  convLoading.value = true
  try {
    conversations.value = await convApi.list()
  } finally {
    convLoading.value = false
  }
}

async function loadMessages() {
  if (!currentConvId.value) {
    messages.value = []
    return
  }
  try {
    const data = await convApi.get(currentConvId.value)
    messages.value = (data.messages || []).map((m: any) => ({
      ...m,
      timeText: formatTime(m.created_at),
      streaming: false,
    }))
    scrollToBottom()
  } catch (err: any) {
    ElMessage.error(err.message || '加载对话失败')
  }
}

function openConversation(id: number) {
  currentConvId.value = id
  loadMessages()
}

function newConversation() {
  currentConvId.value = null
  messages.value = []
  streamError.value = ''
}

function autoGrow() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  })
}

async function sendMessage() {
  const question = input.value.trim()
  if (!question || streaming.value) return
  input.value = ''
  streamError.value = ''
  lastQuestion = question
  autoGrow()

  // ensure a conversation exists
  if (!currentConvId.value) {
    const conv = await convApi.create(question.slice(0, 60))
    currentConvId.value = conv.id
    await loadConversations()
  }

  messages.value.push({ role: 'USER', content: question })
  const assistantMsg = {
    role: 'ASSISTANT',
    content: '',
    evidence_status: '',
    citations: [],
    retrieval_meta: null,
    streaming: true,
    stageText: '正在检索知识…',
    timeText: formatTime(new Date()),
  }
  messages.value.push(assistantMsg)
  scrollToBottom()
  streaming.value = true

  const controller = new AbortController()
  currentController = controller

  await streamSse(
    '/api/chat/stream',
    {
      message: question,
      conversation_id: currentConvId.value,
      kb_ids: selectedKbIds.value.length ? selectedKbIds.value : null,
    },
    {
      onEvent: (event, data) => {
        const m = messages.value[messages.value.length - 1]
        if (event === 'meta') {
          currentConvId.value = data.conversation_id
        } else if (event === 'status') {
          if (m) m.stageText = data.message
        } else if (event === 'answer') {
          if (m) {
            m.content += data.delta
            scrollToBottom()
          }
        } else if (event === 'evidence') {
          if (m) {
            m.evidence_status = data.status
            m.evidence_reason = data.reason
          }
        } else if (event === 'citations') {
          if (m) {
            m.citations = data.citations
            m.retrieval_meta = { ...m.retrieval_meta, ...data.retrieval_meta }
          }
        } else if (event === 'error') {
          streamError.value = data.message || '回答生成失败'
        }
      },
      onError: (err) => {
        streamError.value = err.message || '连接中断，请重试'
      },
      onDone: () => {
        const m = messages.value[messages.value.length - 1]
        if (m) m.streaming = false
        streaming.value = false
        currentController = null
        loadConversations()
        scrollToBottom()
      },
    },
    controller.signal,
  )
}

function retryLast() {
  if (!lastQuestion || streaming.value) return
  messages.value.pop() // remove failed assistant msg
  input.value = lastQuestion
  sendMessage()
}

onMounted(async () => {
  await Promise.all([loadConversations(), kbApi.list().then((list) => (allKbs.value = list))])
  const convParam = route.query.conversation
  if (convParam) {
    currentConvId.value = Number(convParam)
    await loadMessages()
  }
})
</script>

<style scoped>
.chat-page { display: flex; gap: 16px; height: 100%; min-height: 0; }
.conv-list {
  width: 240px; flex-shrink: 0;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-card); display: flex; flex-direction: column; overflow: hidden;
}
.conv-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 16px 10px;
}
.conv-title { font-weight: 700; font-size: 14px; }
.new-conv-btn {
  border: none; background: var(--primary-light); color: var(--primary);
  width: 26px; height: 26px; border-radius: 7px; cursor: pointer; font-size: 15px;
}
.new-conv-btn:hover { background: var(--primary-border); }
.conv-items { flex: 1; overflow-y: auto; padding: 0 8px 10px; }
.conv-item {
  padding: 10px 12px; border-radius: 8px; cursor: pointer; margin-bottom: 2px;
}
.conv-item:hover { background: #f5f6f8; }
.conv-item.active { background: var(--primary-light); }
.conv-item-title {
  font-size: 13px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.conv-item.active .conv-item-title { color: var(--primary); font-weight: 600; }
.conv-item-time { font-size: 11px; color: var(--text-tertiary); margin-top: 3px; }
.conv-empty { padding: 24px 16px; color: var(--text-tertiary); font-size: 12.5px; text-align: center; }
.chat-main {
  flex: 1; min-width: 0; display: flex; flex-direction: column;
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-card);
  overflow: hidden;
}
.scope-bar {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 18px; border-bottom: 1px solid var(--border); flex-wrap: wrap;
}
.scope-label { font-size: 13px; color: var(--text-secondary); flex-shrink: 0; }
.scope-chips { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; flex: 1; }
.scope-chip {
  display: inline-flex; align-items: center; gap: 6px;
  background: var(--primary-light); color: var(--primary);
  border: 1px solid var(--primary-border); border-radius: 999px;
  padding: 4px 10px; font-size: 12.5px; font-weight: 600;
}
.chip-x {
  border: none; background: transparent; color: var(--primary); cursor: pointer;
  font-size: 10px; padding: 0;
}
.add-kb-btn {
  border: 1px dashed var(--border); background: transparent; color: var(--text-secondary);
  border-radius: 999px; padding: 4px 12px; font-size: 12.5px; cursor: pointer;
}
.add-kb-btn:hover { border-color: var(--primary); color: var(--primary); }
.all-kb-btn {
  border: none; background: transparent; color: var(--primary); font-size: 13px;
  cursor: pointer; font-weight: 600; flex-shrink: 0;
}
.all-kb-indicator {
  font-size: 13px; color: var(--primary); font-weight: 600; cursor: pointer; flex-shrink: 0;
}
.messages-area { flex: 1; overflow-y: auto; padding: 22px 26px; }
.msg-row { display: flex; gap: 12px; margin-bottom: 22px; }
.msg-row.user { justify-content: flex-end; }
.msg-bubble {
  max-width: 70%; padding: 11px 16px; border-radius: 14px;
  font-size: 14px; line-height: 1.7; white-space: pre-wrap; word-break: break-word;
}
.user-bubble { background: var(--primary); color: #fff; border-bottom-right-radius: 4px; }
.msg-avatar {
  width: 34px; height: 34px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; font-size: 14px;
}
.user-avatar-sm { background: #e5e7eb; }
.ai-avatar { background: var(--primary); color: #fff; font-size: 12px; }
.msg-body { flex: 1; min-width: 0; }
.evidence-banner {
  display: flex; align-items: flex-start; gap: 10px;
  border: 1px solid var(--border); border-radius: 10px;
  padding: 10px 14px; margin-bottom: 12px; background: #fafafa;
}
.ev-ok { background: var(--green-bg); border-color: #a7f3d0; }
.ev-warn { background: var(--amber-bg); border-color: #fde68a; }
.ev-conflict { background: var(--red-bg); border-color: #fecaca; }
.ev-icon { font-size: 14px; margin-top: 1px; }
.ev-text { flex: 1; font-size: 13px; display: flex; flex-direction: column; gap: 2px; }
.ev-meta { color: var(--text-secondary); font-size: 12px; }
.ev-time { font-size: 11px; color: var(--text-tertiary); flex-shrink: 0; }
.typing-row { display: flex; align-items: center; gap: 8px; color: var(--text-secondary); font-size: 13px; }
.typing-text { animation: pulse 1.4s ease-in-out infinite; }
@keyframes pulse { 50% { opacity: 0.55; } }
.msg-answer { margin-bottom: 10px; }
.retrieval-details {
  border: 1px solid var(--border); border-radius: 10px;
  padding: 10px 14px; margin-bottom: 12px; font-size: 12.5px;
  background: #fafbfc;
}
.retrieval-details summary {
  cursor: pointer; color: var(--text-secondary); font-weight: 600; user-select: none;
}
.rp-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-top: 12px; }
.rp-item { display: flex; flex-direction: column; gap: 2px; }
.rp-k { color: var(--text-tertiary); font-size: 11.5px; }
.rp-v { font-weight: 600; }
.rp-stages { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.rp-stage-chip {
  background: #eef1f6; border-radius: 6px; padding: 3px 8px; font-size: 11.5px;
  color: var(--text-secondary);
}
.rp-note { margin: 8px 0 0; color: var(--green); font-size: 12px; }
.citations-card {
  border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px;
  background: #fafbfc; margin-bottom: 6px;
}
.cit-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.cit-title { font-weight: 700; font-size: 13px; }
.cit-all {
  border: none; background: transparent; color: var(--primary); cursor: pointer;
  font-size: 12px; font-weight: 500;
}
.citation-row {
  display: flex; gap: 10px; padding: 9px 10px; border: 1px solid var(--border);
  border-radius: 8px; margin-bottom: 6px; cursor: pointer; background: #fff;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.citation-row:hover { border-color: var(--primary-border); box-shadow: 0 2px 8px rgba(79, 70, 229, 0.08); }
.citation-row:focus-visible { outline: 2px solid var(--primary); outline-offset: 1px; }
.cit-idx { font-weight: 800; color: var(--primary); font-size: 12.5px; }
.cit-main { flex: 1; min-width: 0; }
.cit-doc-title {
  font-weight: 600; font-size: 13px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
}
.cit-path { font-size: 11.5px; color: var(--text-tertiary); margin-top: 3px; }
.chat-empty {
  height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center;
  color: var(--text-secondary); text-align: center; padding: 20px;
}
.chat-empty-icon {
  width: 64px; height: 64px; border-radius: 18px; background: var(--primary);
  color: #fff; font-size: 24px; display: flex; align-items: center; justify-content: center;
  margin-bottom: 16px;
}
.chat-empty h2 { font-size: 18px; color: var(--text); margin: 0 0 6px; }
.chat-empty p { font-size: 13px; margin: 0 0 20px; }
.suggest-list { display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; }
.suggest-chip {
  border: 1px solid var(--border); background: #fff; border-radius: 999px;
  padding: 8px 16px; font-size: 13px; cursor: pointer; color: var(--text-secondary);
}
.suggest-chip:hover { border-color: var(--primary); color: var(--primary); }
.input-bar { padding: 12px 18px 16px; border-top: 1px solid var(--border); }
.stream-error {
  display: flex; align-items: center; justify-content: space-between;
  background: var(--red-bg); color: var(--red); border-radius: 8px;
  padding: 8px 12px; font-size: 12.5px; margin-bottom: 8px;
}
.retry-btn {
  border: 1px solid var(--red); background: transparent; color: var(--red);
  border-radius: 6px; padding: 2px 12px; cursor: pointer; font-size: 12px;
}
.input-row { display: flex; align-items: flex-end; gap: 10px; }
.attach-btn {
  border: none; background: transparent; font-size: 17px; cursor: pointer;
  color: var(--text-tertiary); padding: 8px 4px;
}
.chat-input {
  flex: 1; border: 1px solid var(--border); border-radius: 10px;
  padding: 11px 14px; font-size: 14px; font-family: inherit; resize: none;
  outline: none; line-height: 1.5; max-height: 160px;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.chat-input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1); }
.send-btn {
  width: 42px; height: 42px; border-radius: 10px; border: none;
  background: var(--primary); color: #fff; font-size: 16px; cursor: pointer;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.send-btn:hover { background: var(--primary-hover); }
.send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.spinner {
  width: 14px; height: 14px; border: 2px solid rgba(79, 70, 229, 0.3);
  border-top-color: var(--primary); border-radius: 50%;
  animation: spin 0.7s linear infinite; display: inline-block;
}
.spinner.sm { width: 13px; height: 13px; }
.spinner.dark { border-color: rgba(255,255,255,0.4); border-top-color: #fff; }
@keyframes spin { to { transform: rotate(360deg); } }
.kb-picker { max-height: 300px; overflow-y: auto; }
.kb-picker-item {
  display: flex; align-items: center; gap: 8px; padding: 9px 10px;
  border-radius: 8px; cursor: pointer; font-size: 13px;
}
.kb-picker-item:hover { background: #f5f6f8; }
.kb-picker-item.disabled { opacity: 0.45; cursor: not-allowed; }
.picker-name { flex: 1; }
.picker-status { font-size: 11px; color: var(--text-tertiary); }
.picker-empty { color: var(--text-tertiary); font-size: 12.5px; text-align: center; }
.picker-hint { color: var(--text-tertiary); font-size: 11px; text-align: center; margin: 8px 0 0; }
@media (max-width: 1023px) {
  .conv-list { display: none; }
  .chat-page { gap: 0; }
}
</style>
