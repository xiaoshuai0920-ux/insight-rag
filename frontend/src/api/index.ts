/** API modules covering every backend endpoint used by the UI. */
import { http } from './client'

// ---------- types ----------
export interface User {
  id: number
  username: string
  email: string
}

export interface KbStats {
  total_documents: number
  available_documents: number
  processing_documents: number
  failed_documents: number
  retrievable_chunks: number
  status: string
}

export interface KnowledgeBase extends KbStats {
  id: number
  name: string
  description: string
  category: string
  updated_at: string | null
}

export interface DocVersion {
  id: number
  version_label: string
  file_version: string
  file_name: string
  file_type: string
  file_size: number
  effective_date: string | null
  processing_status: string
  lifecycle_status: string
  error_message: string | null
  updated_at?: string | null
  created_at?: string | null
}

export interface KbDocument {
  id: number
  title: string
  department: string
  category: string
  updated_at: string | null
  current_version: DocVersion | null
  version_count: number
}

export interface DashboardStats {
  summary: {
    knowledge_bases: number
    total_documents: number
    available_documents: number
    retrievable_chunks: number
    processing_documents: number
    computed_at: string
  }
  recent_knowledge_bases: KnowledgeBase[]
  recent_conversations: {
    id: number
    title: string
    question: string
    kb_names: string[]
    updated_at: string | null
  }[]
}

// ---------- auth ----------
export const authApi = {
  login: (account: string, password: string, remember: boolean) =>
    http.post('/auth/login', { account, password, remember }) as Promise<{ token: string; user: User }>,
  register: (username: string, email: string, password: string) =>
    http.post('/auth/register', { username, email, password }) as Promise<{ token: string; user: User }>,
  me: () => http.get('/auth/me') as Promise<User>,
}

// ---------- knowledge bases ----------
export const kbApi = {
  list: (q = '') => http.get('/knowledge-bases', { params: { q } }) as Promise<KnowledgeBase[]>,
  get: (id: number) => http.get(`/knowledge-bases/${id}`) as Promise<KnowledgeBase>,
  create: (data: { name: string; description: string; category: string }) =>
    http.post('/knowledge-bases', data) as Promise<KnowledgeBase>,
  update: (id: number, data: { name: string; description: string; category: string }) =>
    http.put(`/knowledge-bases/${id}`, data) as Promise<KnowledgeBase>,
  remove: (id: number) => http.delete(`/knowledge-bases/${id}`) as Promise<void>,
  documents: (id: number, q = '') =>
    http.get(`/knowledge-bases/${id}/documents`, { params: { q } }) as Promise<KbDocument[]>,
}

// ---------- documents ----------
export const docApi = {
  upload: (kbId: number, file: File, onProgress?: (pct: number) => void) => {
    const form = new FormData()
    form.append('file', file)
    return http.post('/documents/upload', form, {
      params: { kb_id: kbId },
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (e.total && onProgress) onProgress(Math.round((e.loaded / e.total) * 100))
      },
    }) as Promise<{ document_id: number; version_id: number; processing_status: string }>
  },
  get: (id: number) => http.get(`/documents/${id}`) as Promise<any>,
  remove: (id: number) => http.delete(`/documents/${id}`) as Promise<void>,
  version: (id: number) => http.get(`/document-versions/${id}`) as Promise<any>,
  chunks: (versionId: number, chunkType = 'CHILD') =>
    http.get(`/document-versions/${versionId}/chunks`, { params: { chunk_type: chunkType } }) as Promise<any[]>,
  reindex: (versionId: number) => http.post(`/document-versions/${versionId}/reindex`) as Promise<any>,
  fileUrl: (versionId: number) => `/api/document-versions/${versionId}/file`,
}

// ---------- conversations / chat ----------
export const convApi = {
  list: () => http.get('/conversations') as Promise<{ id: number; title: string; updated_at: string | null }[]>,
  create: (title: string) => http.post('/conversations', { title }) as Promise<any>,
  get: (id: number) => http.get(`/conversations/${id}`) as Promise<any>,
  remove: (id: number) => http.delete(`/conversations/${id}`) as Promise<void>,
}

// ---------- retrieval lab ----------
export interface RetrievalRunPayload {
  kb_ids: number[] | null
  question: string
  strategy: string
  dense_top_k?: number
  bm25_top_k?: number
  rrf_candidate_k?: number
  rrf_constant?: number
  reranker_top_k?: number
  final_context?: number
}

export const labApi = {
  run: (payload: RetrievalRunPayload) => http.post('/retrieval/run', payload) as Promise<any>,
  compare: (payload: RetrievalRunPayload) => http.post('/retrieval/compare', payload) as Promise<any>,
  evaluationRun: (strategy: string) => http.post('/evaluation/run', { strategy }) as Promise<any>,
  evaluationRuns: () => http.get('/evaluation/runs') as Promise<any[]>,
}

// ---------- settings ----------
export const settingsApi = {
  get: () => http.get('/settings') as Promise<any>,
  update: (payload: Record<string, unknown>) => http.put('/settings', payload) as Promise<any>,
  testLlm: () => http.post('/settings/test-llm') as Promise<any>,
  testReranker: () => http.post('/settings/test-reranker') as Promise<any>,
  embeddingImpact: () => http.get('/settings/embedding-impact') as Promise<any>,
  reindex: (provider: string, model: string) =>
    http.post('/settings/reindex', { provider, model }) as Promise<any>,
  reindexStatus: () => http.get('/settings/reindex-status') as Promise<any>,
  retryReindex: (profileId: number) => http.post(`/settings/reindex/${profileId}/retry`) as Promise<any>,
  ollamaModels: () => http.get('/ollama/models') as Promise<any>,
}

// ---------- dashboard ----------
export const statsApi = {
  dashboard: () => http.get('/stats/dashboard') as Promise<DashboardStats>,
}
