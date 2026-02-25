import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Sidebar } from './Sidebar';

import { useAuthStore } from '@/store/authStore';
import { useChatStore } from '@/store/chatStore';

vi.mock('@/store/authStore', () => ({
  useAuthStore: vi.fn(),
}));
vi.mock('@/store/chatStore', () => ({
  useChatStore: vi.fn(),
}));
vi.mock('@/api/client', () => ({
  listJobs: vi.fn().mockResolvedValue([]),
}));
vi.mock('@/components/JobMonitor/JobCard', () => ({
  JobCard: () => <div data-testid="job-card" />,
}));
vi.mock('@/components/Layout/Skeleton', () => ({
  SidebarSkeleton: () => <div data-testid="sidebar-skeleton" />,
  JobCardSkeleton: () => <div data-testid="job-skeleton" />,
}));

const mockedUseAuthStore = vi.mocked(useAuthStore);
const mockedUseChatStore = vi.mocked(useChatStore);

const mockLoadConversations = vi.fn().mockResolvedValue(undefined);
const mockSelectConversation = vi.fn();
const mockNewConversation = vi.fn();

describe('Sidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedUseAuthStore.mockReturnValue({
      user: { display_name: 'Test User', email: 'test@example.com' },
    } as any);
    mockedUseChatStore.mockReturnValue({
      conversations: [
        { conversation_id: 'c1', title: 'PDB Analysis', preview: 'Fetch PDB 1ABC', last_activity: '2025-01-01' },
        { conversation_id: 'c2', title: null, preview: 'Design a binder', last_activity: '2025-01-02' },
      ],
      loadConversations: mockLoadConversations,
      selectConversation: mockSelectConversation,
      newConversation: mockNewConversation,
    } as any);
  });

  it('renders user info', async () => {
    render(<Sidebar />);
    await waitFor(() => {
      expect(screen.getByText('Test User')).toBeInTheDocument();
    });
    expect(screen.getByText('test@example.com')).toBeInTheDocument();
  });

  it('renders new conversation button', async () => {
    render(<Sidebar />);
    await waitFor(() => {
      expect(screen.getByText(/new conversation/i)).toBeInTheDocument();
    });
  });

  it('displays conversation titles in sidebar', async () => {
    render(<Sidebar />);
    await waitFor(() => {
      expect(screen.getByText('PDB Analysis')).toBeInTheDocument();
    });
    // Second conversation has no title, shows preview
    expect(screen.getByText('Design a binder')).toBeInTheDocument();
  });

  it('selects conversation on click', async () => {
    const user = userEvent.setup();
    render(<Sidebar />);

    await waitFor(() => {
      expect(screen.getByText('PDB Analysis')).toBeInTheDocument();
    });

    await user.click(screen.getByText('PDB Analysis'));
    expect(mockSelectConversation).toHaveBeenCalledWith('c1');
  });

  it('creates new conversation on button click', async () => {
    const user = userEvent.setup();
    render(<Sidebar />);

    await waitFor(() => {
      expect(screen.getByText(/new conversation/i)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/new conversation/i));
    expect(mockNewConversation).toHaveBeenCalled();
  });

  it('shows tabs for chats and jobs', async () => {
    render(<Sidebar />);
    await waitFor(() => {
      expect(screen.getByText('Conversations')).toBeInTheDocument();
    });
    expect(screen.getByText(/jobs/i)).toBeInTheDocument();
  });
});
