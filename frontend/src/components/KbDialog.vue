<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? '编辑知识库' : '新建知识库'"
    width="440px"
    :close-on-click-modal="false"
  >
    <el-form label-position="top" @submit.prevent>
      <el-form-item label="名称" required>
        <el-input v-model="form.name" placeholder="例如：财务制度库" maxlength="128" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="3"
          placeholder="简要说明该知识库收录的内容，便于后续检索理解"
          maxlength="500"
        />
      </el-form-item>
      <el-form-item label="分类">
        <el-select v-model="form.category" style="width: 100%">
          <el-option label="人事 (hr)" value="hr" />
          <el-option label="财务 (finance)" value="finance" />
          <el-option label="产品 (product)" value="product" />
          <el-option label="客服 (service)" value="service" />
          <el-option label="采购 (procurement)" value="procurement" />
          <el-option label="信息安全 (compliance)" value="compliance" />
          <el-option label="通用 (general)" value="general" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="!form.name.trim()" @click="handleSave">
        {{ isEdit ? '保存' : '创建' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { kbApi, type KnowledgeBase } from '../api'

const props = defineProps<{ kb?: KnowledgeBase | null }>()
const emit = defineEmits<{ saved: [kb: KnowledgeBase] }>()

const visible = ref(false)
const saving = ref(false)
const isEdit = ref(false)

const form = reactive({ name: '', description: '', category: 'general' })

watch(
  () => props.kb,
  (kb) => {
    if (kb) {
      form.name = kb.name
      form.description = kb.description
      form.category = kb.category || 'general'
      isEdit.value = true
    } else {
      form.name = ''
      form.description = ''
      form.category = 'general'
      isEdit.value = false
    }
  },
)

function open() {
  visible.value = true
}
defineExpose({ open })

async function handleSave() {
  saving.value = true
  try {
    const payload = { name: form.name.trim(), description: form.description.trim(), category: form.category }
    const kb = isEdit.value && props.kb ? await kbApi.update(props.kb.id, payload) : await kbApi.create(payload)
    ElMessage.success(isEdit.value ? '知识库已更新' : '知识库创建成功')
    visible.value = false
    emit('saved', kb)
  } catch (err: any) {
    ElMessage.error(err.message || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>
