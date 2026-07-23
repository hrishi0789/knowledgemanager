// src/api/client.ts
// Typed fetch wrapper with JWT injection + snake_case → camelCase conversion

const BASE_URL = '/api/v1';

// ── snake_case ↔ camelCase conversion ─────────────────────────────────────

function toCamel(s: string): string {
  return s.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
}

function fromCamel(s: string): string {
  return s.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);
}

function deepToCamel(obj: unknown): unknown {
  if (Array.isArray(obj)) return obj.map(deepToCamel);
  if (obj && typeof obj === 'object') {
    return Object.fromEntries(
      Object.entries(obj as Record<string, unknown>).map(([k, v]) => [
        toCamel(k),
        deepToCamel(v),
      ])
    );
  }
  return obj;
}

function deepToSnake(obj: unknown): unknown {
  if (Array.isArray(obj)) return obj.map(deepToSnake);
  if (obj && typeof obj === 'object') {
    return Object.fromEntries(
      Object.entries(obj as Record<string, unknown>).map(([k, v]) => [
        fromCamel(k),
        deepToSnake(v),
      ])
    );
  }
  return obj;
}

// ── Token storage ──────────────────────────────────────────────────────────

export function getToken(): string | null {
  return localStorage.getItem('pkms_token');
}

export function setToken(token: string): void {
  localStorage.setItem('pkms_token', token);
}

export function clearToken(): void {
  localStorage.removeItem('pkms_token');
}

// ── Error type ─────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string
  ) {
    super(detail);
    this.name = 'ApiError';
  }
}

// ── Core fetch ─────────────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  authenticated = true
): Promise<T> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(options.headers ?? {}),
  };

  if (authenticated) {
    const token = getToken();
    if (token) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
    }
  }

  const response = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (response.status === 204) return undefined as unknown as T;

  const json = await response.json().catch(() => ({ detail: response.statusText }));

  if (!response.ok) {
    const detail = (json as { detail?: string }).detail ?? `HTTP ${response.status}`;
    throw new ApiError(response.status, detail);
  }

  return deepToCamel(json) as T;
}

// ── Convenience methods ────────────────────────────────────────────────────

export function apiGet<T>(path: string, authenticated = true): Promise<T> {
  return apiFetch<T>(path, { method: 'GET' }, authenticated);
}

export function apiPost<T>(
  path: string,
  body: unknown,
  authenticated = true
): Promise<T> {
  return apiFetch<T>(
    path,
    { method: 'POST', body: JSON.stringify(deepToSnake(body)) },
    authenticated
  );
}

export function apiDelete(path: string): Promise<void> {
  return apiFetch<void>(path, { method: 'DELETE' });
}

// ── File upload (multipart) ───────────────────────────────────────────────

export async function apiUpload<T>(
  path: string,
  file: File,
  onProgress?: (pct: number) => void
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${BASE_URL}${path}`);

    const token = getToken();
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

    if (onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
      };
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(deepToCamel(JSON.parse(xhr.responseText)) as T);
        } catch {
          reject(new ApiError(xhr.status, 'Invalid JSON response'));
        }
      } else {
        let detail = `HTTP ${xhr.status}`;
        try {
          detail = JSON.parse(xhr.responseText).detail ?? detail;
        } catch {}
        reject(new ApiError(xhr.status, detail));
      }
    };

    xhr.onerror = () => reject(new ApiError(0, 'Network error'));

    const fd = new FormData();
    fd.append('file', file);
    xhr.send(fd);
  });
}
