// src/api/endpoints.ts — One typed function per API endpoint

import {
  apiDelete,
  apiGet,
  apiPost,
  apiUpload,
} from './client';
import type {
  Document,
  DocumentListResponse,
  EvaluationReport,
  GraphOverview,
  GraphSearchResponse,
  HealthResponse,
  LearningGapsResponse,
  LearningPathResponse,
  NeighborsResponse,
  OutboxSummary,
  SearchResponse,
  TokenResponse,
  User,
} from './types';

// ── Auth ───────────────────────────────────────────────────────────────────

export const authApi = {
  register: (email: string, displayName: string, password: string) =>
    apiPost<TokenResponse>('/auth/register', { email, displayName, password }, false),

  login: (email: string, password: string) =>
    apiPost<TokenResponse>('/auth/login', { email, password }, false),

  me: () => apiGet<User>('/auth/me'),
};

// ── Documents ──────────────────────────────────────────────────────────────

export const documentsApi = {
  upload: (file: File, onProgress?: (pct: number) => void) =>
    apiUpload<Document>('/documents/upload', file, onProgress),

  list: (params?: {
    page?: number;
    pageSize?: number;
    status?: string;
    category?: string;
  }) => {
    const q = new URLSearchParams();
    if (params?.page) q.set('page', String(params.page));
    if (params?.pageSize) q.set('page_size', String(params.pageSize));
    if (params?.status) q.set('status', params.status);
    if (params?.category) q.set('category', params.category);
    const qs = q.toString();
    return apiGet<DocumentListResponse>(`/documents${qs ? `?${qs}` : ''}`);
  },

  get: (id: string) => apiGet<Document>(`/documents/${id}`),

  delete: (id: string) => apiDelete(`/documents/${id}`),

  correctCategory: (id: string, correctCategory: string) =>
    apiPost<Document>(`/documents/${id}/correct-category`, { documentId: id, correctCategory }),
};

// ── Search ─────────────────────────────────────────────────────────────────

export const searchApi = {
  semantic: (query: string, topK = 10, category?: string) =>
    apiPost<SearchResponse>('/search', { query, topK, category }),

  graph: (
    query: string,
    opts?: {
      hops?: number;
      decay?: number;
      gateThreshold?: number;
      topKSeeds?: number;
    }
  ) =>
    apiPost<GraphSearchResponse>('/search/graph', {
      query,
      hops: opts?.hops ?? 3,
      decay: opts?.decay ?? 0.7,
      gateThreshold: opts?.gateThreshold ?? 0.25,
      topKSeeds: opts?.topKSeeds ?? 5,
    }),
};

// ── Graph ──────────────────────────────────────────────────────────────────

export const graphApi = {
  overview: () => apiGet<GraphOverview>('/graph/overview'),

  neighbors: (nodeKey: string, depth = 1) =>
    apiGet<NeighborsResponse>(`/graph/neighbors/${encodeURIComponent(nodeKey)}?depth=${depth}`),

  presets: () => apiGet<Array<{ id: string; label: string; cypher: string }>>('/graph/cypher-presets'),
};

// ── Analytics ──────────────────────────────────────────────────────────────

export const analyticsApi = {
  learningPath: (conceptKey: string) =>
    apiPost<LearningPathResponse>('/analytics/learning-path', { conceptKey }),

  gaps: (topN = 10) =>
    apiGet<LearningGapsResponse>(`/analytics/gaps?top_n=${topN}`),
};

// ── Categories ─────────────────────────────────────────────────────────────

export const categoriesApi = {
  list: () => apiGet<string[]>('/categories'),
};

// ── Admin ──────────────────────────────────────────────────────────────────

export const adminApi = {
  health: () => apiGet<HealthResponse>('/admin/health', false),

  outbox: () => apiGet<OutboxSummary>('/admin/outbox'),

  runEvaluation: () => apiPost<EvaluationReport>('/admin/evaluation', {}),
};
