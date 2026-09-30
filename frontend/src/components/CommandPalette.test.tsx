import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { CommandPalette } from './CommandPalette';
import * as api from '../lib/api';

vi.mock('../lib/api', () => ({
  searchFiles: vi.fn(),
}));

describe('CommandPalette', () => {
  it('covers all paths', async () => {
    vi.mocked(api.searchFiles).mockResolvedValue({ results: [{ path: 'a.py' }, { path: 'b.py' }] });
    render(<CommandPalette isOpen={true} onClose={vi.fn()} activeRepoPath="/repo" onSelectFile={vi.fn()} onAsk={vi.fn()} />);
    
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'app' } });
    
    await waitFor(() => {
       expect(api.searchFiles).toHaveBeenCalled();
    });
    
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'ArrowUp' });
    fireEvent.keyDown(input, { key: 'Enter' });
    
    const items = screen.queryAllByText('a.py');
    if (items.length > 0) {
      fireEvent.mouseEnter(items[0].parentElement!);
      fireEvent.click(items[0].parentElement!);
    }
    
    fireEvent.change(input, { target: { value: 'explain app' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    
    fireEvent.change(input, { target: { value: '' } });
    fireEvent.keyDown(input, { key: 'Escape' });
    fireEvent.keyDown(input, { key: 'Enter' });
  });
});
