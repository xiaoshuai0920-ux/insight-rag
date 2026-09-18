<template>
  <div>
    <div class="hero">
      <h1 class="hero-title">设置</h1>
      <p class="hero-sub">配置模型与系统参数，打造适合您团队的知识问答能力</p>
    </div>

    <div v-if="dirty" class="dirty-bar">
      <span class="dirty-dot" aria-hidden="true"></span> 有未保存更改
      <div class="dirty-actions">
        <el-button @click="resetForm">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveAll">保存更改</el-button>
      </div>
    </div>

    <!-- LLM -->
    <div class="card section-card">
      <div class="sec-head">
        <div>
          <h3 class="sec-title">LLM 配置</h3>
          <p class="sec-hint">配置用于生成回答的大语言模型</p>
        </div>
        <span class="live-note">ⓘ 保存后立即生效</span>
      </div>

      <div class="llm-grid">
        <div class="llm-left">
          <label class="cfg-label">选择提供商</label>
          <div class="provider-cards">
            <button
              class="provider-card"
              :class="{ active: form.llm_provider === 'deepseek' }"
              role="radio"
              :aria-checked="form.llm_provider === 'deepseek'"
              @click="form.llm_provider = 'deepseek'"
            >
              <span class="provider-radio" aria-hidden="true"></span>
              <span class="provider-name">🐋 DeepSeek</span>
              <span class="provider-desc">云端大模型（deepseek-chat）</span>
              <span class="provider-status" :class="settings.deepseek?.configured ? 'ok' : 'bad'">
                {{ settings.deepseek?.configured ? 'API Key 已配置' : '未配置 API Key' }}
              </span>
            </button>
            <button
              class="provider-card"
              :class="{ active: form.llm_provider === 'ollama' }"
              role="radio"
              :aria-checked="form.llm_provider === 'ollama'"
              @click="form.llm_provider = 'ollama'"
            >
              <span class="provider-radio" aria-hidden="true"></span>
              <span class="provider-name">🦙 Ollama</span>
              <span class="provider-desc">本地部署的开源模型</span>
              <span class="provider-status" :class="settings.ollama?.available ? 'ok' : 'bad'">
                {{ settings.ollama?.available ? '服务可用' : '服务不可用' }}
              </span>
            </button>
          </div>
        </div>

        <div class="llm-right">
          <div class="llm-field-row">
            <div class="llm-field">
              <label class="cfg-label">部署方式</label>
              <el-select v-model="form.llm_provider" style="width: 100%">
                <el-option label="本地模型 (Ollama)" value="ollama" />
                <el-option label="DeepSeek" value="deepseek" />
              </el-select>
            </div>
            <div class="llm-field">
              <label class="cfg-label">服务地址</label>
              <el-input v-model="form.llm_endpoint" :disabled="form.llm_provider !== 'ollama'" placeholder="http://localhost:11434" />
            </div>
          </div>
          <div class="llm-field-row">
            <div class="llm-field">
              <label class="cfg-label">模型</label>
              <el-select
                v-model="form.llm_model"
                style="width: 100%"
                filterable
                allow-create
                default-first-option
                placeholder="选择或输入模型名"
              >
                <el-option v-for="m in llmModels" :key="m" :label="m" :value="m" />
              </el-select>
            </div>
            <div class="llm-field">
              <label class="cfg-label">状态</label>
              <div class="conn-status">
                <span class="conn-dot" :class="llmConnected ? 'ok' : 'bad'" aria-hidden="true"></span>
                {{ llmConnected ? '已连接' : '未连接' }}
                <span v-if="llmLatency" class="conn-latency">响应时间 {{ llmLatency }}ms</span>
              </div>
            </div>
          </div>
          <button class="btn-ghost test-btn" :disabled="testingLlm" @click="testLlm">
            <span v-if="testingLlm" class="spinner dark"></span>
            <span v-else aria-hidden="true">▷</span> 测试连接
          </button>
          <p v-if="llmTestMessage" class="test-message" :class="llmConnected ? 'ok' : 'bad'">{{ llmTestMessage }}</p>
        </div>
      </div>
    </div>

    <!-- Embedding -->
    <div class="card section-card">
      <div class="sec-head">
        <div>
          <h3 class="sec-title">Embedding 配置</h3>
          <p class="sec-hint">配置用于文本向量化的模型，影响检索效果</p>
        </div>
      </div>

      <div class="emb-grid">
        <div class="emb-left">
          <div class="llm-field-row">
            <div class="llm-field">
              <label class="cfg-label">当前模型</label>
              <el-select v-model="form.embedding_model" style="width: 100%" filterable allow-create default-first-option>
                <el-option label="nomic-embed-text (Ollama)" value="nomic-embed-text" />
                <el-option v-for="m in otherEmbeddingModels" :key="m" :label="m" :value="m" />
              </el-select>
            </div>
            <div class="llm-field">
              <label class="cfg-label">向量维度</label>
              <el-input :model-value="settings.active_profile?.dimension ?? '-'" disabled />
            </div>
          </div>
          <p class="emb-provider-note">
            Provider: {{ settings.active_profile?.provider || form.embedding_provider }}
            <template v-if="settings.active_profile?.status === 'ACTIVE'"> · ACTIVE 索引服务中</template>
            <template v-else-if="settings.active_profile"> · {{ settings.active_profile.status }}</template>
          </p>
        </div>

        <div class="emb-warning-panel">
          <div class="emb-warning-head">
            <span class="warn-icon" aria-hidden="true">⚠</span>
            <b>更换 Embedding 模型将需要重新构建所有知识库的索引</b>
          </div>
          <p class="emb-warning-text">
            新的向量表示与旧模型不兼容，必须重新对所有文档进行向量化处理。此过程可能需要较长时间；重建期间旧索引继续提供服务。
          </p>
          <div class="emb-impact-grid">
            <div class="impact-item">
              <span class="impact-icon" aria-hidden="true">📖</span>
              <div><div class="impact-value">{{ impact?.affected_knowledge_bases ?? '-' }}</div><div class="impact-label">受影响知识库</div></div>
            </div>
            <div class="impact-item">
              <span class="impact-icon" aria-hidden="true">📄</span>
              <div><div class="impact-value">{{ impact?.affected_documents ?? '-' }}</div><div class="impact-label">受影响文档</div></div>
            </div>
            <div class="impact-item">
              <span class="impact-icon" aria-hidden="true">🗂</span>
              <div><div class="impact-value">{{ formatNumber(impact?.affected_chunks) }}</div><div class="impact-label">受影响可检索片段</div></div>
            </div>
          </div>
          <div class="emb-actions">
            <el-button @click="showImpact">查看受影响知识库</el-button>
            <el-button type="primary" plain :loading="reindexing" @click="confirmReindex">
              ↻ 更换并重建索引
            </el-button>
          </div>
          <div v-if="reindexStatus?.rebuilding_profile" class="rebuild-status" :class="reindexStatus.rebuilding_profile.status">
            <template v-if="reindexStatus.rebuilding_profile.status === 'BUILDING'">
              <span class="spinner dark"></span> 正在重建新索引（{{ reindexStatus.rebuilding_profile.provider }} / {{ reindexStatus.rebuilding_profile.model_name }}）— 旧索引继续服务
            </template>
            <template v-else-if="reindexStatus.rebuilding_profile.status === 'FAILED'">
              ⚠ 重建失败：{{ reindexStatus.rebuilding_profile.error_message }}
              <el-button size="small" style="margin-left: 10px" @click="retryReindex">重试</el-button>
            </template>
          </div>
        </div>
      </div>
    </div>

    <!-- Reranker -->
    <div class="card section-card">
      <div class="sec-head">
        <div>
          <h3 class="sec-title">Reranker 配置</h3>
          <p class="sec-hint">配置用于重排检索结果的模型，提升回答相关性</p>
        </div>
      </div>
      <div class="reranker-row">
        <div class="reranker-toggle">
          <el-switch v-model="form.reranker_enabled" />
          <div>
            <div class="reranker-label">启用 Reranker</div>
            <div class="reranker-desc">对检索到的候选片段进行重排序</div>
          </div>
        </div>
        <div class="llm-field">
          <label class="cfg-label">选择提供商</label>
          <el-input model-value="BAAI (本地)" disabled />
        </div>
        <div class="llm-field">
          <label class="cfg-label">模型</label>
          <el-select v-model="form.reranker_model" style="width: 100%">
            <el-option label="BAAI/bge-reranker-base" value="BAAI/bge-reranker-base" />
            <el-option label="BAAI/bge-reranker-v2-m3" value="BAAI/bge-reranker-v2-m3" />
          </el-select>
        </div>
        <div class="reranker-actions">
          <el-button :disabled="testingReranker" @click="testReranker">
            <span v-if="testingReranker" class="spinner dark"></span> 测试模型
          </el-button>
          <p class="reranker-note">保存后影响新的检索请求，不会重建已有索引。</p>
        </div>
      </div>
      <p v-if="rerankerMessage" class="test-message" :class="rerankerOk ? 'ok' : 'bad'">{{ rerankerMessage }}</p>
    </div>

    <!-- Impact dialog -->
    <el-dialog v-model="impactVisible" title="受影响知识库" width="460px">
      <div v-if="impact?.kb_list?.length">
        <div v-for="kb in impact.kb_list" :key="kb.id" class="impact-kb-row">
          <span>{{ kb.name }}</span>
          <span class="muted">{{ kb.documents }} 个文档</span>
        </div>
      </div>
      <p v-else class="muted">当前没有受影响的知识库数据。</p>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { settingsApi } from '../api'

const settings = ref<any>({})
const impact = ref<any>(null)
const reindexStatus = ref<any>(null)
const dirty = ref(false)
const saving = ref(false)
const testingLlm = ref(false)
const llmConnected = ref(false)
const llmLatency = ref<number | null>(null)
const llmTestMessage = ref('')
const testingReranker = ref(false)
const rerankerOk = ref(false)
const rerankerMessage = ref('')
const impactVisible = ref(false)
const reindexing = ref(false)
const llmModels = ref<string[]>([])
const otherEmbeddingModels = ref<string[]>([])

const form = reactive({
  llm_provider: 'ollama',
  llm_model: '',
  llm_endpoint: '',
  embedding_provider: 'ollama',
  embedding_model: 'nomic-embed-text',
  reranker_enabled: false,
  reranker_model: 'BAAI/bge-reranker-base',
})

function formatNumber(n?: number | null) {
  if (n === null || n === undefined) return '-'
  return n.toLocaleString('zh-CN')
}

async function load() {
  settings.value = await settingsApi.get()
  form.llm_provider = settings.value.llm_provider || 'ollama'
  form.llm_model = settings.value.llm_model || ''
  form.llm_endpoint = settings.value.llm_endpoint || settings.value.ollama_base_url || ''
  form.embedding_provider = settings.value.embedding_provider || 'ollama'
  form.embedding_model = settings.value.embedding_model || 'nomic-embed-text'
  form.reranker_enabled = !!settings.value.reranker_enabled
  form.reranker_model = settings.value.reranker_model || 'BAAI/bge-reranker-base'
  llmConnected.value = !!settings.value.ollama?.available
  if (settings.value.openai_compatible_configured) {
    otherEmbeddingModels.value = ['text-embedding-3-small', 'text-embedding-3-large']
  }
  impact.value = await settingsApi.embeddingImpact()
  reindexStatus.value = await settingsApi.reindexStatus()
  const ollama = await settingsApi.ollamaModels()
  if (ollama?.available) llmModels.value = ollama.models || []
  dirty.value = false
}

watch(form, () => {
  dirty.value = true
})

function resetForm() {
  load()
}

async function saveAll() {
  saving.value = true
  try {
    await settingsApi.update({ ...form })
    ElMessage.success('配置已保存，已立即生效')
    await load()
  } catch (err: any) {
    ElMessage.error(err.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function testLlm() {
  testingLlm.value = true
  llmTestMessage.value = ''
  const t0 = performance.now()
  try {
    const resp = await settingsApi.testLlm()
    llmConnected.value = !!resp.ok
    if (resp.ok) {
      llmLatency.value = Math.round(performance.now() - t0)
      llmTestMessage.value = `${resp.message}${resp.model_available === false ? '（注意：所选模型不在可用列表中）' : ''}`
    } else {
      llmTestMessage.value = resp.message
    }
  } catch (err: any) {
    llmConnected.value = false
    llmTestMessage.value = err.message || '测试失败'
  } finally {
    testingLlm.value = false
  }
}

async function testReranker() {
  testingReranker.value = true
  rerankerMessage.value = ''
  try {
    const resp = await settingsApi.testReranker()
    rerankerOk.value = !!resp.ok
    rerankerMessage.value = resp.message
  } catch (err: any) {
    rerankerOk.value = false
    rerankerMessage.value = err.message || '测试失败'
  } finally {
    testingReranker.value = false
  }
}

async function showImpact() {
  impact.value = await settingsApi.embeddingImpact()
  impactVisible.value = true
}

async function confirmReindex() {
  try {
    await ElMessageBox.confirm(
      '将创建新的 Embedding 索引并在后台重建所有向量。重建期间旧索引继续服务检索，全部完成后自动切换。确认开始？',
      '更换并重建索引',
      { confirmButtonText: '开始重建', cancelButtonText: '取消', type: 'warning' },
    )
    reindexing.value = true
    const provider = form.embedding_provider
    const model = form.embedding_model
    const resp = await settingsApi.reindex(provider, model)
    if (resp.status === 'noop') {
      ElMessage.info(resp.message)
    } else {
      ElMessage.success('重建任务已启动，可在本页查看进度')
    }
    reindexStatus.value = await settingsApi.reindexStatus()
  } catch {
    /* cancelled */
  } finally {
    reindexing.value = false
  }
}

async function retryReindex() {
  const profile = reindexStatus.value?.rebuilding_profile
  if (!profile) return
  try {
    await settingsApi.retryReindex(profile.id)
    ElMessage.success('已重新开始重建')
    reindexStatus.value = await settingsApi.reindexStatus()
  } catch (err: any) {
    ElMessage.error(err.message || '重试失败')
  }
}

onMounted(load)

// poll reindex status while building
setInterval(async () => {
  if (reindexStatus.value?.rebuilding_profile?.status === 'BUILDING') {
    reindexStatus.value = await settingsApi.reindexStatus()
  }
}, 5000)
</script>

<style scoped>
.hero { margin-bottom: 16px; }
.hero-title { font-size: 22px; font-weight: 800; margin: 0 0 4px; }
.hero-sub { color: var(--text-secondary); margin: 0; font-size: 13px; }
.dirty-bar {
  display: flex; align-items: center; gap: 8px;
  background: var(--amber-bg); border: 1px solid #fde68a; color: var(--amber);
  border-radius: 10px; padding: 10px 16px; margin-bottom: 16px; font-size: 13px; font-weight: 600;
}
.dirty-dot { width: 8px; height: 8px; border-radius: 50%; background: #f59e0b; display: inline-block; }
.dirty-actions { margin-left: auto; display: flex; gap: 8px; }
.section-card { padding: 22px 24px; margin-bottom: 18px; }
.sec-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.sec-title { margin: 0 0 4px; font-size: 15px; font-weight: 700; }
.sec-hint { margin: 0; font-size: 12.5px; color: var(--text-secondary); }
.live-note { font-size: 12px; color: var(--text-tertiary); }
.cfg-label { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px; font-weight: 600; }
.llm-grid { display: grid; grid-template-columns: 280px 1fr; gap: 24px; }
.provider-cards { display: flex; flex-direction: column; gap: 10px; }
.provider-card {
  border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px;
  text-align: left; cursor: pointer; background: #fff; position: relative;
  display: flex; flex-direction: column; gap: 3px;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.provider-card:hover { border-color: var(--primary-border); }
.provider-card.active {
  border-color: var(--primary);
  box-shadow: 0 0 0 1px var(--primary);
}
.provider-radio {
  position: absolute; top: 12px; right: 12px;
  width: 15px; height: 15px; border-radius: 50%;
  border: 2px solid var(--border);
}
.provider-card.active .provider-radio { border-color: var(--primary); background: var(--primary); }
.provider-name { font-weight: 700; font-size: 14px; }
.provider-desc { font-size: 12px; color: var(--text-secondary); }
.provider-status { font-size: 11px; margin-top: 3px; font-weight: 600; }
.provider-status.ok { color: var(--green); }
.provider-status.bad { color: var(--text-tertiary); }
.llm-field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 12px; }
.conn-status { display: flex; align-items: center; gap: 7px; font-size: 13px; padding-top: 5px; }
.conn-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.conn-dot.ok { background: #10b981; }
.conn-dot.bad { background: #d1d5db; }
.conn-latency { color: var(--text-tertiary); font-size: 12px; }
.test-btn { margin-top: 4px; }
.test-message { font-size: 12.5px; margin: 10px 0 0; }
.test-message.ok { color: var(--green); }
.test-message.bad { color: var(--red); }
.emb-grid { display: grid; grid-template-columns: 300px 1fr; gap: 24px; }
.emb-provider-note { font-size: 12px; color: var(--text-tertiary); margin: 8px 0 0; }
.emb-warning-panel {
  background: var(--amber-bg); border: 1px solid #fde68a; border-radius: 12px; padding: 16px 20px;
}
.emb-warning-head { display: flex; align-items: center; gap: 8px; font-size: 13.5px; color: var(--amber); }
.emb-warning-text { font-size: 12.5px; color: #92400e; margin: 8px 0 14px; line-height: 1.7; }
.emb-impact-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.impact-item {
  background: #fff; border: 1px solid #fde68a; border-radius: 10px;
  padding: 12px 14px; display: flex; align-items: center; gap: 10px;
}
.impact-icon { font-size: 18px; }
.impact-value { font-size: 18px; font-weight: 800; }
.impact-label { font-size: 11px; color: var(--text-tertiary); }
.emb-actions { margin-top: 14px; display: flex; gap: 10px; }
.rebuild-status {
  margin-top: 12px; border-radius: 8px; padding: 9px 12px; font-size: 12.5px;
}
.rebuild-status.BUILDING { background: var(--primary-light); color: var(--primary); }
.rebuild-status.FAILED { background: var(--red-bg); color: var(--red); }
.reranker-row { display: grid; grid-template-columns: 220px 1fr 1fr 1fr; gap: 16px; align-items: start; }
.reranker-toggle { display: flex; gap: 10px; align-items: center; }
.reranker-label { font-weight: 700; font-size: 13.5px; }
.reranker-desc { font-size: 11.5px; color: var(--text-tertiary); margin-top: 2px; }
.reranker-note { font-size: 11px; color: var(--text-tertiary); margin: 6px 0 0; }
.spinner {
  width: 12px; height: 12px; border: 2px solid rgba(79,70,229,0.3); border-top-color: var(--primary);
  border-radius: 50%; animation: spin 0.7s linear infinite; display: inline-block;
}
.spinner.dark { border-color: rgba(255,255,255,0.4); border-top-color: #fff; }
@keyframes spin { to { transform: rotate(360deg); } }
.muted { color: var(--text-tertiary); }
.impact-kb-row {
  display: flex; justify-content: space-between; padding: 9px 4px;
  border-bottom: 1px solid #f3f4f6; font-size: 13px;
}
@media (max-width: 1023px) {
  .llm-grid, .emb-grid { grid-template-columns: 1fr; }
  .reranker-row { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 767px) {
  .reranker-row { grid-template-columns: 1fr; }
  .emb-impact-grid { grid-template-columns: 1fr; }
}
</style>
