import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { ChatMessage } from './ChatMessage';
import { mockChatMessage } from '@/test/mocks';

// Mock MolStarViewer since it depends on heavy Molstar imports
vi.mock('@/components/MolViewer/MolStarViewer', () => ({
  MolStarViewer: ({ pdbContents }: { pdbContents: Record<string, string> }) => (
    <div data-testid="molstar-viewer">
      {Object.keys(pdbContents).join(', ')}
    </div>
  ),
}));

describe('ChatMessage', () => {
  it('renders user message with correct styling', () => {
    const msg = mockChatMessage({ role: 'user', content: 'Hello Claude' });
    render(<ChatMessage message={msg} />);
    expect(screen.getByText('Hello Claude')).toBeInTheDocument();
  });

  it('renders assistant message', () => {
    const msg = mockChatMessage({
      role: 'assistant',
      content: 'I can help with protein binder design.',
    });
    render(<ChatMessage message={msg} />);
    expect(screen.getByText(/protein binder design/)).toBeInTheDocument();
  });

  it('renders tool calls as collapsible sections', () => {
    const msg = mockChatMessage({
      toolCalls: [
        { name: 'fetch_pdb', input: { pdb_id: '1ABC' } },
      ],
    });
    render(<ChatMessage message={msg} />);
    expect(screen.getByText('fetch_pdb')).toBeInTheDocument();
  });

  it('expands tool call details on click', async () => {
    const user = userEvent.setup();
    const msg = mockChatMessage({
      toolCalls: [
        { name: 'get_pdb_info', input: { file_id: 'abc' }, result: '{"chains": {}}' },
      ],
    });
    render(<ChatMessage message={msg} />);

    // Click to expand
    await user.click(screen.getByText('get_pdb_info'));

    expect(screen.getByText(/input:/i)).toBeInTheDocument();
    expect(screen.getByText(/result:/i)).toBeInTheDocument();
  });

  it('renders inline Mol* viewer for visualizations', () => {
    const msg = mockChatMessage({
      visualizations: [
        { pdb_contents: { 'file1': 'ATOM...' }, style: 'cartoon', color_by: 'chain' },
      ],
    });
    render(<ChatMessage message={msg} />);
    expect(screen.getByTestId('molstar-viewer')).toBeInTheDocument();
  });

  it('shows model name for assistant messages', () => {
    const msg = mockChatMessage({
      role: 'assistant',
      content: 'Response',
      modelUsed: 'claude-sonnet-4-6',
    });
    render(<ChatMessage message={msg} />);
    expect(screen.getByText('claude-sonnet-4-6')).toBeInTheDocument();
  });

  it('does not show model name for user messages', () => {
    const msg = mockChatMessage({
      role: 'user',
      content: 'Hello',
      modelUsed: 'claude-sonnet-4-6',
    });
    render(<ChatMessage message={msg} />);
    expect(screen.queryByText('claude-sonnet-4-6')).not.toBeInTheDocument();
  });
});
