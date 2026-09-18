<template>
  <div class="empty-state">
    <div class="empty-icon" aria-hidden="true">{{ icon }}</div>
    <h3 class="empty-title">{{ title }}</h3>
    <p class="empty-desc">{{ description }}</p>
    <button v-if="actionLabel" class="btn-primary" @click="$emit('action')">{{ actionLabel }}</button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  icon?: string
  title: string
  description?: string
  actionLabel?: string
}>()

defineEmits<{ action: [] }>()
</script>

<style scoped>
.empty-state {
  text-align: center;
  padding: 56px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.empty-icon {
  font-size: 36px;
  width: 72px;
  height: 72px;
  border-radius: 20px;
  background: #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 6px;
}
.empty-title {
  font-size: 16px;
  font-weight: 700;
  margin: 0;
}
.empty-desc {
  color: var(--text-secondary);
  font-size: 13px;
  margin: 0 0 12px;
  max-width: 380px;
  line-height: 1.6;
}
</style>
