/**
 * Shared mock factories for tests.
 */

import type { ChatMessage, UserProfile, Conversation } from '@/types';

export function mockUser(overrides?: Partial<UserProfile>): UserProfile {
  return {
    user_id: 'user-123',
    email: 'test@example.com',
    display_name: 'Test User',
    is_admin: false,
    created_at: '2025-01-01T00:00:00Z',
    ...overrides,
  };
}

export function mockChatMessage(overrides?: Partial<ChatMessage>): ChatMessage {
  return {
    id: `msg-${Date.now()}`,
    role: 'assistant',
    content: 'Hello! How can I help you with protein design?',
    ...overrides,
  };
}

export function mockConversation(overrides?: Partial<Conversation>): Conversation {
  return {
    conversation_id: 'conv-123',
    title: 'Test Conversation',
    preview: 'First message preview...',
    last_activity: '2025-01-01T12:00:00Z',
    ...overrides,
  };
}
