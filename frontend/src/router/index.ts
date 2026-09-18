import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '../api/client'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../pages/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/terms',
      name: 'terms',
      component: () => import('../pages/TermsView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('../layouts/MainLayout.vue'),
      children: [
        { path: '', redirect: '/dashboard' },
        { path: 'dashboard', name: 'dashboard', component: () => import('../pages/DashboardView.vue'), meta: { title: '工作台' } },
        { path: 'knowledge-bases', name: 'kb-list', component: () => import('../pages/KnowledgeBasesView.vue'), meta: { title: '知识库' } },
        { path: 'knowledge-bases/:id', name: 'kb-detail', component: () => import('../pages/KnowledgeBaseDetailView.vue'), meta: { title: '知识库详情' } },
        { path: 'chat', name: 'chat', component: () => import('../pages/ChatView.vue'), meta: { title: 'AI 问答' } },
        { path: 'lab', name: 'lab', component: () => import('../pages/RetrievalLabView.vue'), meta: { title: 'Retrieval Lab' } },
        { path: 'settings', name: 'settings', component: () => import('../pages/SettingsView.vue'), meta: { title: '设置' } },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

router.beforeEach((to) => {
  if (!to.meta.public && !getToken()) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && getToken()) {
    return { name: 'dashboard' }
  }
})

export default router
