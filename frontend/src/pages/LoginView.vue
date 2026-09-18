<template>
  <div class="login-page">
    <div class="login-brand">
      <div class="brand-logo"><span class="brand-mark">▶</span> InsightRAG</div>
      <p class="brand-sub">企业级多知识库智能检索与问答平台</p>
    </div>

    <div class="login-card">
      <template v-if="mode === 'login'">
        <h1 class="login-title">登录 InsightRAG</h1>
        <p class="login-sub">欢迎回来，继续探索企业知识的无限可能</p>

        <form @submit.prevent="handleLogin">
          <label class="field-label" for="login-account">邮箱 / 用户名</label>
          <div class="input-wrap">
            <span class="input-icon">👤</span>
            <input
              id="login-account"
              v-model="account"
              type="text"
              placeholder="请输入邮箱地址或用户名"
              autocomplete="username"
              :disabled="auth.loading"
            />
          </div>

          <label class="field-label" for="login-password">密码</label>
          <div class="input-wrap">
            <span class="input-icon">🔒</span>
            <input
              id="login-password"
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              placeholder="请输入密码"
              autocomplete="current-password"
              :disabled="auth.loading"
            />
            <button
              type="button"
              class="toggle-password"
              :aria-label="showPassword ? '隐藏密码' : '显示密码'"
              @click="showPassword = !showPassword"
            >
              {{ showPassword ? '🙈' : '👁' }}
            </button>
          </div>
          <p class="field-hint">至少 8 位，包含字母和数字</p>

          <div class="form-row">
            <label class="remember-label">
              <input v-model="remember" type="checkbox" />
              记住我
            </label>
            <span class="register-link">
              <a href="#" @click.prevent="mode = 'register'">注册账号</a>
              <span class="divider">|</span>
              <span class="sso-disabled" title="未来支持企业 SSO">未来支持企业 SSO</span>
            </span>
          </div>

          <div v-if="authError" class="form-error" role="alert">
            <span class="error-icon">⚠</span> {{ authError }}
          </div>

          <button type="submit" class="btn-primary login-btn" :disabled="auth.loading || !account || !password">
            <span v-if="auth.loading" class="spinner" aria-hidden="true"></span>
            {{ auth.loading ? '登录中…' : '登录' }}
          </button>
        </form>
      </template>

      <template v-else>
        <h1 class="login-title">注册 InsightRAG</h1>
        <p class="login-sub">创建账号，开始构建你的企业知识库</p>
        <form @submit.prevent="handleRegister">
          <label class="field-label" for="reg-username">用户名</label>
          <div class="input-wrap">
            <span class="input-icon">👤</span>
            <input id="reg-username" v-model="regUsername" type="text" placeholder="2-64 个字符" :disabled="auth.loading" />
          </div>
          <label class="field-label" for="reg-email">邮箱</label>
          <div class="input-wrap">
            <span class="input-icon">✉</span>
            <input id="reg-email" v-model="regEmail" type="email" placeholder="name@company.com" :disabled="auth.loading" />
          </div>
          <label class="field-label" for="reg-password">密码</label>
          <div class="input-wrap">
            <span class="input-icon">🔒</span>
            <input
              id="reg-password"
              v-model="regPassword"
              :type="showPassword ? 'text' : 'password'"
              placeholder="请输入密码"
              :disabled="auth.loading"
            />
          </div>
          <p class="field-hint">至少 8 位，包含字母和数字</p>
          <div v-if="authError" class="form-error" role="alert">
            <span class="error-icon">⚠</span> {{ authError }}
          </div>
          <button
            type="submit"
            class="btn-primary login-btn"
            :disabled="auth.loading || !regUsername || !regEmail || !regPassword"
          >
            <span v-if="auth.loading" class="spinner" aria-hidden="true"></span>
            {{ auth.loading ? '注册中…' : '注册' }}
          </button>
          <p class="switch-mode">已有账号？<a href="#" @click.prevent="mode = 'login'">返回登录</a></p>
        </form>
      </template>

      <p class="agreement">继续使用即表示同意</p>
      <p class="agreement-links">
        <router-link to="/terms">服务协议</router-link>
        <span class="divider">|</span>
        <router-link to="/terms">隐私政策</router-link>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const mode = ref<'login' | 'register'>('login')
const account = ref('')
const password = ref('')
const remember = ref(true)
const showPassword = ref(false)
const authError = ref('')

const regUsername = ref('')
const regEmail = ref('')
const regPassword = ref('')

watch([account, password, regUsername, regEmail, regPassword], () => {
  authError.value = ''
})

function validatePassword(pw: string): string | null {
  if (!/^(?=.*[A-Za-z])(?=.*\d).{8,}$/.test(pw)) return '密码至少 8 位，包含字母和数字'
  return null
}

async function handleLogin() {
  authError.value = ''
  try {
    await auth.login(account.value.trim(), password.value, remember.value)
    router.push((route.query.redirect as string) || '/dashboard')
  } catch (err: any) {
    authError.value = err.message || '账号或密码不正确'
  }
}

async function handleRegister() {
  authError.value = validatePassword(regPassword.value) || ''
  if (authError.value) return
  try {
    await auth.register(regUsername.value.trim(), regEmail.value.trim(), regPassword.value)
    router.push('/dashboard')
  } catch (err: any) {
    authError.value = err.message || '注册失败'
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  background:
    radial-gradient(600px 400px at 90% 10%, rgba(79, 70, 229, 0.08), transparent),
    radial-gradient(500px 380px at 5% 90%, rgba(79, 70, 229, 0.07), transparent),
    #f7f8fc;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.login-brand {
  text-align: center;
  margin-bottom: 28px;
}
.brand-logo {
  font-size: 30px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  letter-spacing: -0.5px;
}
.brand-mark {
  width: 42px;
  height: 42px;
  border-radius: 11px;
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  color: #fff;
  font-size: 19px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.brand-sub {
  color: var(--text-secondary);
  margin: 10px 0 0;
  font-size: 14px;
}
.login-card {
  width: 420px;
  max-width: 100%;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: 0 8px 30px rgba(17, 24, 39, 0.06);
  padding: 32px 36px;
}
.login-title {
  font-size: 22px;
  margin: 0 0 6px;
  font-weight: 800;
}
.login-sub {
  color: var(--text-secondary);
  margin: 0 0 24px;
  font-size: 13px;
}
.field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  margin: 16px 0 6px;
}
.input-wrap {
  display: flex;
  align-items: center;
  border: 1px solid var(--border);
  border-radius: var(--radius-input);
  padding: 0 12px;
  background: #fff;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.input-wrap:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.12);
}
.input-icon {
  color: var(--text-tertiary);
  font-size: 14px;
  margin-right: 8px;
}
.input-wrap input {
  flex: 1;
  border: none;
  outline: none;
  padding: 11px 0;
  font-size: 14px;
  background: transparent;
}
.toggle-password {
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--text-tertiary);
  padding: 4px;
}
.field-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 6px 0 0;
}
.form-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 16px 0 4px;
  font-size: 13px;
}
.remember-label {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: var(--text);
}
.remember-label input {
  accent-color: var(--primary);
  width: 15px;
  height: 15px;
}
.register-link a {
  color: var(--primary);
  text-decoration: none;
  font-weight: 600;
}
.sso-disabled {
  color: var(--text-tertiary);
}
.divider {
  margin: 0 8px;
  color: var(--border);
}
.form-error {
  background: var(--red-bg);
  color: var(--red);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13px;
  margin-top: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.login-btn {
  width: 100%;
  justify-content: center;
  padding: 12px;
  font-size: 15px;
  margin-top: 16px;
}
.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  display: inline-block;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.switch-mode {
  text-align: center;
  margin: 14px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
}
.switch-mode a {
  color: var(--primary);
  font-weight: 600;
  text-decoration: none;
}
.agreement {
  text-align: center;
  color: var(--text-tertiary);
  font-size: 12px;
  margin: 26px 0 6px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}
.agreement-links {
  text-align: center;
  font-size: 13px;
  margin: 0;
}
.agreement-links a {
  color: var(--primary);
  text-decoration: none;
  font-weight: 500;
}
@media (max-width: 480px) {
  .login-card {
    padding: 24px 20px;
  }
}
</style>
