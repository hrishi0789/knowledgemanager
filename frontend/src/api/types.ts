// src/api/types.ts — TypeScript interfaces mirroring backend Pydantic schemas

export interface User {
  id: string;
  email: string;
  displayName: string;
  createdAt: string;
}

export interface TokenResponse {
  accessToken: string;
  tokenType: string;
  expiresIn: number;
}

export type DocumentStatus =
  | 'UPLOADED'
  | 'EXTRACTING'
  | 'EXTRACTED'
  | 'CHUNKED'
  | 'INDEXED'
  | 'FAILED';

export interface Document {
  id: string;
  title: string;
  kind: string;
  mimeType: string;
  byteSize: number;
  status: DocumentStatus;
  category: string | null;
  categoryConf: number | null;
  clusterId: string | null;
  createdAt: string;
  updatedAt: string;
  errorLog: string | null;
}

export interface DocumentListResponse {
  items: Document[];
  total: number;
  page: number;
  pageSize: number;
}

export interface SearchHit {
  chunkId: string;
  documentId: string;
  documentTitle: string;
  score: number;
  preview: string;
  category: string | null;
}

export interface SearchResponse {
  hits: SearchHit[];
  total: number;
  query: string;
}

export interface GraphNode {
  key: string;
  label: string;
  name: string;
  activation: number;
  pagerank: number | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  weight: number | null;
}

export interface GraphSearchResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  seedKeys: string[];
  degraded: boolean;
}

export interface GraphOverview {
  documentCount: number;
  conceptCount: number;
  technologyCount: number;
  edgeCount: number;
}

export interface NeighborNode {
  key: string;
  label: string;
  name: string;
  pagerank: number | null;
  relationshipType: string;
  relationshipWeight: number | null;
}

export interface NeighborsResponse {
  center: GraphNode;
  neighbors: NeighborNode[];
}

export interface LearningPathResponse {
  path: string[];
  hasCycle: boolean;
}

export interface LearningGap {
  conceptKey: string;
  conceptName: string;
  dependents: number;
  pagerank: number;
}

export interface LearningGapsResponse {
  gaps: LearningGap[];
}

export interface StoreHealth {
  postgres: boolean;
  chroma: boolean;
  neo4j: boolean;
  redis: boolean;
}

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'down';
  stores: StoreHealth;
  version: string;
}

export interface OutboxSummary {
  pending: number;
  processing: number;
  failed: number;
}

export interface EvaluationReport {
  hitAt1: number;
  hitAt5: number;
  hitAt10: number;
  mrr: number;
  ndcgAt10: number;
  classificationF1: number | null;
  evalTimeSeconds: number;
}
