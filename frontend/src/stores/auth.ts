import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi, type User } from '../api'
import { clearToken, setToken, getToken } from '../api/client'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const loading = ref(false)

  function isLoggedIn() {
    return !!getToken()
  }

  async function fetchMe() {
    if (!getToken()) return
    try {
      user.value = await authApi.me()
    } catch {
      user.value = null
    }
  }

  async function login(account: string, password: string, remember: boolean) {
    loading.value = true
    try {
      const resp = await authApi.login(account, password, remember)
      setToken(resp.token)
      user.value = resp.user
    } finally {
      loading.value = false
    }
  }

  async function register(username: string, email: string, password: string) {
    loading.value = true
    try {
      const resp = await authApi.register(username, email, password)
      setToken(resp.token)
      user.value = resp.user
    } finally {
      loading.value = false
    }
  }

  function logout() {
    clearToken()
    user.value = null
  }

  return { user, loading, isLoggedIn, fetchMe, login, register, logout }
})
