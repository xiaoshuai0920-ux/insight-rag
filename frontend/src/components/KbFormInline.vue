<template>
  <el-form v-if="kb" label-position="top" class="kb-form-inline">
    <div class="form-grid">
      <el-form-item label="名称">
        <el-input v-model="name" maxlength="128" />
      </el-form-item>
      <el-form-item label="分类">
        <el-select v-model="category" style="width: 100%">
          <el-option label="人事 (hr)" value="hr" />
          <el-option label="财务 (finance)" value="finance" />
          <el-option label="产品 (product)" value="product" />
          <el-option label="客服 (service)" value="service" />
          <el-option label="采购 (procurement)" value="procurement" />
          <el-option label="信息安全 (compliance)" value="compliance" />
          <el-option label="通用 (general)" value="general" />
        </el-select>
      </el-form-item>
    </div>
    <el-form-item label="描述">
      <el-input v-model="description" type="textarea" :rows="3" maxlength="500" />
    </el-form-item>
    <div class="form-actions">
      <el-button type="primary" :loading="saving" :disabled="!name.trim()" @click="save">保存更改</el-button>
      <span v-if="dirty" class="unsaved-hint">有未保存更改</span>
    </div>
  </el-form>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { kbApi, type KnowledgeBase } from '../api'

const props = defineProps<{ kb: KnowledgeBase | null }>()
const emit = defineEmits<{ saved: [] }>()

const name = ref('')
const description = ref('')
const category = ref('general')
const dirty = ref(false)
const saving = ref(false)

watch(
  () => props.kb,
  (kb) => {
    if (kb) {
      name.value = kb.name
      description.value = kb.description
      category.value = kb.category || 'general'
      dirty.value = false
    }
  },
  { immediate: true },
)

watch([name, description, category], () => {
  if (props.kb) {
    dirty.value =
      name.value !== props.kb.name ||
      description.value !== props.kb.description ||
      category.value !== props.kb.category
  }
})

async function save() {
  if (!props.kb) return
  saving.value = true
  try {
    await kbApi.update(props.kb.id, {
      name: name.value.trim(),
      description: description.value.trim(),
      category: category.value,
    })
    dirty.value = false
    ElMessage.success('知识库已保存')
    emit('saved')
  } catch (err: any) {
    ElMessage.error(err.message || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.form-actions { display: flex; align-items: center; gap: 14px; }
.unsaved-hint { color: var(--amber); font-size: 13px; }
@media (max-width: 767px) { .form-grid { grid-template-columns: 1fr; } }
</style>
