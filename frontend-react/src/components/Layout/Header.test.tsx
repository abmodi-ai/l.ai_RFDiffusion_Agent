import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Header } from './Header';

import { useAuthStore } from '@/store/authStore';
vi.mock('@/store/authStore', () => ({
  useAuthStore: vi.fn(),
}));
const mockedUseAuthStore = vi.mocked(useAuthStore);

const mockLogout = vi.fn();

describe('Header', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedUseAuthStore.mockReturnValue({ logout: mockLogout } as any);
  });

  it('renders app title', () => {
    render(<Header />);
    expect(screen.getByText('Ligant.ai')).toBeInTheDocument();
  });

  it('renders subtitle', () => {
    render(<Header />);
    expect(screen.getByText(/protein binder design/i)).toBeInTheDocument();
  });

  it('calls logout when sign out is clicked', async () => {
    const user = userEvent.setup();
    render(<Header />);

    await user.click(screen.getByText(/sign out/i));
    expect(mockLogout).toHaveBeenCalled();
  });
});
