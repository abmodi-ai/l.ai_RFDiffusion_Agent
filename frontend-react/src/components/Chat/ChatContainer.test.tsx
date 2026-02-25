import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ChatContainer } from './ChatContainer';

// Mock child components to isolate ChatContainer logic
vi.mock('@/components/Chat/ChatInput', () => ({
  ChatInput: () => <div data-testid="chat-input" />,
}));

vi.mock('@/components/Chat/ChatMessage', () => ({
  ChatMessage: ({ message }: { message: { content: string } }) => (
    <div data-testid="chat-message">{message.content}</div>
  ),
}));

vi.mock('@/components/Layout/Skeleton', () => ({
  ChatSkeleton: () => <div data-testid="chat-skeleton" />,
}));

import { useChatStore } from '@/store/chatStore';
vi.mock('@/store/chatStore', () => ({
  useChatStore: vi.fn(),
}));
const mockedUseChatStore = vi.mocked(useChatStore);

const defaultState = {
  messages: [] as any[],
  isStreaming: false,
  isLoadingHistory: false,
  conversations: [],
  conversationId: null,
  error: null,
  sendMessage: vi.fn(),
  loadConversations: vi.fn(),
  selectConversation: vi.fn(),
  newConversation: vi.fn(),
  clearError: vi.fn(),
};

describe('ChatContainer', () => {
  beforeEach(() => {
    mockedUseChatStore.mockReturnValue(defaultState as any);
  });

  it('shows empty state when no messages', () => {
    render(<ChatContainer />);
    expect(screen.getByText(/start a conversation/i)).toBeInTheDocument();
  });

  it('shows loading skeleton when loading history', () => {
    mockedUseChatStore.mockReturnValue({ ...defaultState, isLoadingHistory: true } as any);
    render(<ChatContainer />);
    expect(screen.getByTestId('chat-skeleton')).toBeInTheDocument();
    expect(screen.queryByText(/start a conversation/i)).not.toBeInTheDocument();
  });

  it('renders messages when available', () => {
    mockedUseChatStore.mockReturnValue({
      ...defaultState,
      messages: [
        { id: '1', role: 'user', content: 'Hello' },
        { id: '2', role: 'assistant', content: 'Hi there!' },
      ],
    } as any);

    render(<ChatContainer />);
    const msgs = screen.getAllByTestId('chat-message');
    expect(msgs).toHaveLength(2);
  });

  it('shows streaming indicator when streaming', () => {
    mockedUseChatStore.mockReturnValue({
      ...defaultState,
      messages: [{ id: '1', role: 'user', content: 'Hello' }],
      isStreaming: true,
    } as any);

    render(<ChatContainer />);
    expect(screen.getByText(/processing/i)).toBeInTheDocument();
  });

  it('renders ChatInput component', () => {
    render(<ChatContainer />);
    expect(screen.getByTestId('chat-input')).toBeInTheDocument();
  });
});
