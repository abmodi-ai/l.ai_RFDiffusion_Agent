/**
 * HTTP + SSE client with JWT auth for the Ligant.ai backend.
 */

import type { AuthResponse, Conversation, JobInfo, UserProfile } from '@/types';

const API_BASE = '/api';

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
  return headers;
}

async function handleResponse<T>(res: Response): Promise<T> {
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
  return fetch(`${API_BASE}/chat/message`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
    }),
  });
}

export async function getConversationHistory(
  conversationId: string,
): Promise<unknown[]> {
  const res = await fetch(`${API_BASE}/chat/${conversationId}/history`, {
    headers: authHeaders(),
  });
  return handleResponse<unknown[]>(res);
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
 */
export function streamJobProgress(jobId: string): EventSource {
  const token = getToken();
  // EventSource doesn't support custom headers, so use query param workaround
  // The backend should accept the token via query param for SSE endpoints
  return new EventSource(`${API_BASE}/job/${jobId}/stream?token=${token}`);
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
