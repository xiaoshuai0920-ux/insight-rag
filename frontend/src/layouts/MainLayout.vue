<template>
  <div class="app-shell" v-if="!isLoginRoute">
    <aside class="sidebar">
      <div class="sidebar-logo">
        <div class="logo-mark">▶</div>
        <span class="logo-text">InsightRAG</span>
      </div>
      <nav class="sidebar-nav" aria-label="主导航">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: isActive(item) }"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span class="nav-label">{{ item.label }}</span>
          <span v-if="item.badge" class="lab-badge">{{ item.badge }}</span>
        </router-link>
      </nav>
      <div class="sidebar-user">
        <div class="user-avatar">{{ avatarChar }}</div>
        <div class="user-info">
          <div class="user-name">{{ auth.user?.username || '用户' }}</div>
          <div class="user-plan">企业版</div>
        </div>
        <button class="logout-btn" aria-label="退出登录" title="退出登录" @click="handleLogout">⎋</button>
      </div>
    </aside>
    <div class="main-area">
      <header class="page-header">
        <div>
          <span class="page-header-title">{{ pageTitle }}</span>
          <span v-if="pageSubtitle" class="page-header-sub">{{ pageSubtitle }}</span>
        </div>
        <slot name="header-action" />
      </header>
      <main class="page-body">
        <router-view />
      </main>
    </div>
  </div>
  <router-view v-else />
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const navItems = [
  { path: '/dashboard', label: '工作台', icon: '⌂' },
  { path: '/knowledge-bases', label: '知识库', icon: '▤' },
  { path: '/chat', label: 'AI 问答', icon: '💬' },
  { path: '/lab', label: 'Retrieval Lab', icon: '⚗', badge: 'LAB' },
  { path: '/settings', label: '设置', icon: '⚙' },
]

const isLoginRoute = computed(() => route.meta.public === true)
const pageTitle = computed(() => (route.meta.title as string) || '')
const pageSubtitle = computed(() => {
  const map: Record<string, string> = {
    '/chat': '基于企业知识库生成带来源的回答',
    '/lab': '分析不同检索策略的召回效果与排序变化',
  }
  return map[route.path] || ''
})

const avatarChar = computed(() => (auth.user?.username || 'U').charAt(0).toUpperCase())

function isActive(item: { path: string }) {
  if (item.path === '/knowledge-bases') {
    return route.path === '/knowledge-bases' || route.path.startsWith('/knowledge-bases/')
  }
  return route.path === item.path
}

watch(
  () => auth.isLoggedIn(),
  () => {
    if (auth.isLoggedIn() && !auth.user) auth.fetchMe()
  },
  { immediate: true },
)

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>
