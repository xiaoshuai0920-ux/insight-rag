/** Typed API client with JWT auth + SSE stream helper. */
import axios from 'axios'

export const TOKEN_KEY = 'insightrag_token'

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export const http = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

http.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (resp) => resp.data,
  (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail || error.message || '请求失败'
    if (status === 401 && !location.pathname.startsWith('/login')) {
      clearToken()
      location.href = '/login'
    }
    return Promise.reject(new Error(typeof detail === 'string' ? detail : JSON.stringify(detail)))
  },
)

export interface SseCallbacks {
  onEvent: (event: string, data: any) => void
  onError?: (err: Error) => void
  onDone?: () => void
}

/** POST-based SSE reader (fetch ReadableStream, no EventSource CORS limits). */
export async function streamSse(
  url: string,
  body: unknown,
  callbacks: SseCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const token = getToken()
  let resp: Response
  try {
    resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
      signal,
    })
  } catch (err: any) {
    if (err?.name !== 'AbortError') callbacks.onError?.(new Error('无法连接服务器，请检查网络或后端服务'))
    callbacks.onDone?.()
    return
  }
  if (!resp.ok || !resp.body) {
    let message = `请求失败 (HTTP ${resp.status})`
    try {
      const data = await resp.json()
      message = data?.detail || message
    } catch {
      /* ignore */
    }
    callbacks.onError?.(new Error(message))
    callbacks.onDone?.()
    return
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finished = false
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const blocks = buffer.split('\n\n')
      buffer = blocks.pop() || ''
      for (const block of blocks) {
        const lines = block.split('\n')
        let event = 'message'
        let data = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) event = line.slice(7).trim()
          else if (line.startsWith('data: ')) data += line.slice(6)
        }
        if (data) {
          let parsed: any = data
          try {
            parsed = JSON.parse(data)
          } catch {
            /* keep raw string */
          }
          callbacks.onEvent(event, parsed)
          if (event === 'done') finished = true
        }
      }
    }
  } catch (err: any) {
    if (err?.name !== 'AbortError') {
      callbacks.onError?.(new Error('连接中断，请重试'))
    }
  } finally {
    if (!finished) callbacks.onDone?.()
    else callbacks.onDone?.()
  }
}
