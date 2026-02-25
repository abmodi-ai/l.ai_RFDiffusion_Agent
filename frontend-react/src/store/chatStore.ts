/**
 * Zustand store for chat messages and conversations.
 */

import { create } from 'zustand';
import type {
  ChatMessage,
  Conversation,
  ToolCallInfo,
  VisualizationData,
} from '@/types';
import * as api from '@/api/client';

interface ChatState {
  messages: ChatMessage[];
  conversations: Conversation[];
  conversationId: string | null;
  isStreaming: boolean;
  isLoadingHistory: boolean;
  error: string | null;

  sendMessage: (text: string) => Promise<void>;
  loadConversations: () => Promise<void>;
  selectConversation: (id: string) => Promise<void>;
  newConversation: () => void;
  clearError: () => void;
}

let messageIdCounter = 0;
function nextId(): string {
  return `msg-${Date.now()}-${++messageIdCounter}`;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  conversations: [],
  conversationId: null,
  isStreaming: false,
  isLoadingHistory: false,
  error: null,

  sendMessage: async (text: string) => {
    const { conversationId } = get();
    set({ isStreaming: true, error: null });

    // Add user message immediately
    const userMsg: ChatMessage = {
      id: nextId(),
      role: 'user',
      content: text,
    };
    set((s) => ({ messages: [...s.messages, userMsg] }));

    // Create placeholder assistant message
    const assistantId = nextId();
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      toolCalls: [],
      visualizations: [],
    };
    set((s) => ({ messages: [...s.messages, assistantMsg] }));

    try {
      const response = await api.sendChatMessage(
        text,
        conversationId ?? undefined,
      );

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${response.status}`);
      }

      if (!response.body) {
        throw new Error('No response body');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        let eventType = '';
        let eventData = '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            eventData = line.slice(6);
          } else if (line === '' && eventType && eventData) {
            // Process complete event
            try {
              const data = JSON.parse(eventData);
              _processSSE(set, get, assistantId, eventType, data);
            } catch {
              // Ignore malformed events
            }
            eventType = '';
            eventData = '';
          }
        }
      }
    } catch (err) {
      set({ error: (err as Error).message });
    } finally {
      set({ isStreaming: false });
    }
  },

  loadConversations: async () => {
    try {
      const conversations = await api.listConversations();
      set({ conversations });
    } catch {
      // Silently fail
    }
  },

  selectConversation: async (id: string) => {
    set({ conversationId: id, messages: [], isLoadingHistory: true });
    try {
      const history = await api.getConversationHistory(id);
      const messages: ChatMessage[] = (history as Array<{ id: string; role: string; content: string; model_used?: string; created_at: string }>).map((m) => ({
        id: m.id,
        role: m.role as 'user' | 'assistant',
        content: m.content,
        modelUsed: m.model_used,
        timestamp: m.created_at,
      }));
      set({ messages, isLoadingHistory: false });
    } catch (err) {
      set({ error: (err as Error).message, isLoadingHistory: false });
    }
  },

  newConversation: () => {
    set({ conversationId: null, messages: [] });
  },

  clearError: () => set({ error: null }),
}));

function _processSSE(
  set: (fn: (s: ChatState) => Partial<ChatState>) => void,
  get: () => ChatState,
  assistantId: string,
  eventType: string,
  data: unknown,
): void {
  const updateAssistant = (
    updater: (msg: ChatMessage) => ChatMessage,
  ) => {
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === assistantId ? updater(m) : m,
      ),
    }));
  };

  switch (eventType) {
    case 'conversation_id': {
      const d = data as { conversation_id: string };
      set(() => ({ conversationId: d.conversation_id }));
      break;
    }
    case 'text': {
      const text = data as string;
      updateAssistant((m) => ({
        ...m,
        content: m.content + text,
      }));
      break;
    }
    case 'tool_call': {
      const tc = data as ToolCallInfo;
      updateAssistant((m) => ({
        ...m,
        toolCalls: [...(m.toolCalls ?? []), tc],
      }));
      break;
    }
    case 'tool_result': {
      const tr = data as { name: string; result: string };
      updateAssistant((m) => ({
        ...m,
        toolCalls: (m.toolCalls ?? []).map((tc) =>
          tc.name === tr.name && !tc.result
            ? { ...tc, result: tr.result }
            : tc,
        ),
      }));
      break;
    }
    case 'visualization': {
      const viz = data as VisualizationData;
      updateAssistant((m) => ({
        ...m,
        visualizations: [...(m.visualizations ?? []), viz],
      }));
      break;
    }
    case 'title': {
      const d = data as { title: string };
      const { conversationId } = get();
      if (conversationId) {
        set((s) => ({
          conversations: s.conversations.map((c) =>
            c.conversation_id === conversationId
              ? { ...c, title: d.title }
              : c,
          ),
        }));
      }
      break;
    }
    case 'done': {
      const d = data as { model_used: string };
      updateAssistant((m) => ({
        ...m,
        modelUsed: d.model_used,
      }));
      // Refresh conversations list to pick up new conversation
      get().loadConversations();
      break;
    }
  }
}
