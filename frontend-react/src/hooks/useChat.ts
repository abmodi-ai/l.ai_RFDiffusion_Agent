/**
 * useChat hook — wraps the chat store for convenience.
 *
 * This is a thin wrapper; the actual SSE streaming logic lives in chatStore.
 */

import { useChatStore } from '@/store/chatStore';

export function useChat() {
  const {
    messages,
    isStreaming,
    conversationId,
    error,
    sendMessage,
    clearError,
  } = useChatStore();

  return {
    messages,
    isStreaming,
    conversationId,
    error,
    sendMessage,
    clearError,
  };
}
