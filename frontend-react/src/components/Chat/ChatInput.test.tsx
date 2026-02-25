import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ChatInput } from './ChatInput';

import { useChatStore } from '@/store/chatStore';
vi.mock('@/store/chatStore', () => ({
  useChatStore: vi.fn(),
}));
const mockedUseChatStore = vi.mocked(useChatStore);

const mockSendMessage = vi.fn();

describe('ChatInput', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedUseChatStore.mockReturnValue({
      sendMessage: mockSendMessage,
      isStreaming: false,
    } as any);
  });

  it('renders textarea and send button', () => {
    render(<ChatInput />);
    expect(screen.getByPlaceholderText(/ask about protein/i)).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('sends message on button click', async () => {
    const user = userEvent.setup();
    render(<ChatInput />);

    const textarea = screen.getByPlaceholderText(/ask about protein/i);
    await user.type(textarea, 'Fetch PDB 1ABC');
    await user.click(screen.getByRole('button'));

    expect(mockSendMessage).toHaveBeenCalledWith('Fetch PDB 1ABC');
  });

  it('sends message on Enter key', async () => {
    const user = userEvent.setup();
    render(<ChatInput />);

    const textarea = screen.getByPlaceholderText(/ask about protein/i);
    await user.type(textarea, 'Hello{Enter}');

    expect(mockSendMessage).toHaveBeenCalledWith('Hello');
  });

  it('does not send on Shift+Enter (allows newline)', async () => {
    const user = userEvent.setup();
    render(<ChatInput />);

    const textarea = screen.getByPlaceholderText(/ask about protein/i);
    await user.type(textarea, 'Line 1{Shift>}{Enter}{/Shift}Line 2');

    expect(mockSendMessage).not.toHaveBeenCalled();
  });

  it('does not send empty messages', async () => {
    const user = userEvent.setup();
    render(<ChatInput />);

    await user.click(screen.getByRole('button'));

    expect(mockSendMessage).not.toHaveBeenCalled();
  });

  it('disables input while streaming', () => {
    mockedUseChatStore.mockReturnValue({
      sendMessage: mockSendMessage,
      isStreaming: true,
    } as any);

    render(<ChatInput />);
    expect(screen.getByPlaceholderText(/ask about protein/i)).toBeDisabled();
  });
});
