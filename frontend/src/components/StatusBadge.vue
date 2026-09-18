<template>
  <span class="status-badge" :class="cls">
    <span v-if="icon" aria-hidden="true">{{ icon }}</span>
    {{ label }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { statusClass } from '../utils/format'

const props = defineProps<{ status: string; label?: string }>()

const cls = computed(() => statusClass(props.status))
const label = computed(() => props.label || props.status)
const icon = computed(() => {
  switch (props.status.toUpperCase()) {
    case 'READY':
    case 'CURRENT':
    case 'SUFFICIENT':
      return '✔'
    case 'UPDATING':
    case 'PARSING':
    case 'CHUNKING':
    case 'INDEXING':
    case 'NEEDS_REINDEX':
      return '↻'
    case 'PARTIAL':
    case 'FAILED':
    case 'CONFLICTING':
      return '⚠'
    case 'INSUFFICIENT':
      return 'ℹ'
    default:
      return ''
  }
})
</script>
