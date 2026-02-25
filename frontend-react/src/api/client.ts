/**
 * HTTP + SSE client with JWT auth for the Ligant.ai backend.
 */

import type { AuthResponse, ChatMessageMetadata, Conversation, JobInfo, UserProfile } from '@/types';

// In local dev, Vite proxies /api to the backend.
// In production (GCP), set VITE_API_BASE to the ngrok URL, e.g. "https://xyz.ngrok-free.app/api"
const API_BASE = import.meta.env.VITE_API_BASE || '/api';

function getToken(): string | null {
  return localStorage.getItem('ligant_token');
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  // Skip ngrok's browser warning interstitial for API calls
  if (API_BASE.includes('ngrok')) {
    headers['ngrok-skip-browser-warning'] = '1';
  }
  return headers;
}

/**
 * Handle API responses.  On 401 (token expired / revoked) automatically
 * clears the stored token so the auth store picks up the change and
 * redirects to the login screen.
 */
async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    localStorage.removeItem('ligant_token');
    // Dispatch a storage event so other tabs/the auth store react
    window.dispatchEvent(new Event('ligant:auth-expired'));
    const body = await res.json().catch(() => ({ detail: 'Session expired' }));
    throw new Error(body.detail || 'Session expired — please sign in again.');
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export async function register(
  email: string,
  password: string,
  displayName: string,
): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, display_name: displayName }),
  });
  return handleResponse<AuthResponse>(res);
}

export async function login(
  email: string,
  password: string,
): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  return handleResponse<AuthResponse>(res);
}

export async function logout(): Promise<void> {
  await fetch(`${API_BASE}/auth/logout`, {
    method: 'POST',
    headers: authHeaders(),
  });
}

export async function getMe(): Promise<UserProfile> {
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: authHeaders(),
  });
  return handleResponse<UserProfile>(res);
}

// ── Chat ─────────────────────────────────────────────────────────────────────

/**
 * Send a chat message and return a ReadableStream for SSE events.
 */
export async function sendChatMessage(
  message: string,
  conversationId?: string,
): Promise<Response> {
  const res = await fetch(`${API_BASE}/chat/message`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
    }),
  });
  // Check for auth expiry on the SSE endpoint too
  if (res.status === 401) {
    localStorage.removeItem('ligant_token');
    window.dispatchEvent(new Event('ligant:auth-expired'));
    throw new Error('Session expired — please sign in again.');
  }
  return res;
}

export interface HistoryMessage {
  id: string;
  role: string;
  content: string;
  model_used?: string;
  metadata?: ChatMessageMetadata | null;
  created_at: string;
}

export async function getConversationHistory(
  conversationId: string,
): Promise<HistoryMessage[]> {
  const res = await fetch(`${API_BASE}/chat/${conversationId}/history`, {
    headers: authHeaders(),
  });
  return handleResponse<HistoryMessage[]>(res);
}

/**
 * Fetch PDB file content by file_id (JWT auth).
 */
export async function getPdbContent(
  fileId: string,
): Promise<{ file_id: string; content: string }> {
  const res = await fetch(`${API_BASE}/chat/pdb/${fileId}/content`, {
    headers: authHeaders(),
  });
  return handleResponse(res);
}

/**
 * Fetch multiple PDB files and return a map of file_id → content.
 */
export async function getPdbContents(
  fileIds: string[],
): Promise<Record<string, string>> {
  const results = await Promise.all(
    fileIds.map((id) => getPdbContent(id).catch(() => null)),
  );
  const map: Record<string, string> = {};
  for (const r of results) {
    if (r) map[r.file_id] = r.content;
  }
  return map;
}

/**
 * Persist an auto-generated visualization message to the DB.
 */
export async function saveAutoVisualizationMessage(
  conversationId: string,
  jobId: string,
  outputPdbIds: string[],
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/${conversationId}/auto-viz`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ job_id: jobId, output_pdb_ids: outputPdbIds }),
  });
  await handleResponse(res);
}

export async function listConversations(): Promise<Conversation[]> {
  const res = await fetch(`${API_BASE}/chat/conversations`, {
    headers: authHeaders(),
  });
  return handleResponse<Conversation[]>(res);
}

// ── Jobs ─────────────────────────────────────────────────────────────────────

export async function listJobs(): Promise<JobInfo[]> {
  const res = await fetch(`${API_BASE}/jobs`, {
    headers: authHeaders(),
  });
  return handleResponse<JobInfo[]>(res);
}

/**
 * Returns an EventSource-like SSE connection for job progress.
 * Adds ngrok-skip-browser-warning via query param to avoid ngrok interstitial page.
 */
export function streamJobProgress(jobId: string): EventSource {
  const token = getToken();
  const params = new URLSearchParams();
  if (token) params.set('token', token);
  // Tell ngrok to skip its browser warning page for SSE connections
  params.set('ngrok-skip-browser-warning', '1');
  return new EventSource(`${API_BASE}/job/${jobId}/stream?${params.toString()}`);
}

// ── File Upload ─────────────────────────────────────────────────────────────

export async function uploadPdb(file: File): Promise<{ file_id: string; filename: string }> {
  const formData = new FormData();
  formData.append('file', file);

  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/upload-pdb`, {
    method: 'POST',
    headers,
    body: formData,
  });
  return handleResponse(res);
}
