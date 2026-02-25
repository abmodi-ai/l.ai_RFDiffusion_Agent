// ── Auth ─────────────────────────────────────────────────────────────────────

export interface AuthResponse {
  token: string;
  user_id: string;
  email: string;
  display_name: string | null;
}

export interface UserProfile {
  user_id: string;
  email: string;
  display_name: string | null;
  is_admin: boolean;
  created_at: string;
}

// ── Chat ─────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  toolCalls?: ToolCallInfo[];
  visualizations?: VisualizationData[];
  modelUsed?: string;
  timestamp?: string;
  jobId?: string;
}

export interface ToolCallInfo {
  name: string;
  input: Record<string, unknown>;
  result?: string;
}

export interface VisualizationData {
  pdb_contents: Record<string, string>;
  style: string;
  color_by: string;
}

/** Metadata stored in DB alongside assistant messages */
export interface ChatMessageMetadata {
  tool_calls?: ToolCallInfo[];
  visualizations?: VisualizationMeta[];
}

/** Lightweight viz reference (file_ids only, no PDB text) */
export interface VisualizationMeta {
  file_ids: string[];
  style: string;
  color_by: string;
}

export interface Conversation {
  conversation_id: string;
  title: string | null;
  preview: string;
  last_activity: string | null;
}

// ── SSE Events ──────────────────────────────────────────────────────────────

export type SSEEventType =
  | 'conversation_id'
  | 'text'
  | 'tool_call'
  | 'tool_result'
  | 'visualization'
  | 'title'
  | 'done';

export interface SSEEvent {
  event: SSEEventType;
  data: unknown;
}

// ── Jobs ─────────────────────────────────────────────────────────────────────

export interface JobInfo {
  job_id: string;
  backend_job_id: string | null;
  status: string;
  contigs: string | null;
  num_designs: number;
  params: Record<string, unknown> | null;
  started_at: string | null;
  completed_at: string | null;
  duration_secs: number | null;
  error_message: string | null;
  result_summary: Record<string, unknown> | null;
  created_at: string;
}

export interface JobProgress {
  job_id: string;
  status: string;
  progress: number | null;
  message: string | null;
}
