import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { EmptyWorkspace } from './EmptyWorkspace';

describe('EmptyWorkspace', () => {
  it('gives the repository path input an accessible name', () => {
    render(<EmptyWorkspace defaultRepoPath="" onScan={vi.fn()} loading={false} />);
    expect(screen.getByLabelText('Repository path')).not.toBeNull();
  });

  it('covers all paths with and without loading', () => {
    const onScan = vi.fn();
    const { rerender } = render(<EmptyWorkspace defaultRepoPath="/test" onScan={onScan} loading={false} />);
    
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: '/foo' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    fireEvent.keyDown(input, { key: 'a' });
    
    const btn = screen.getByRole('button');
    fireEvent.click(btn);

    rerender(<EmptyWorkspace defaultRepoPath="/test" onScan={onScan} loading={true} />);
  });

  it('renders previously scanned repositories as accessible buttons', () => {
    const onSelectRepo = vi.fn();
    render(
      <EmptyWorkspace
        defaultRepoPath=""
        onScan={vi.fn()}
        loading={false}
        repositories={[{ name: 'backend', root_path: '/workspace/backend', files: 27 }]}
        onSelectRepo={onSelectRepo}
      />
    );

    const repoBtn = screen.getByRole('button', { name: /backend.*\/workspace\/backend/i });
    fireEvent.click(repoBtn);
    expect(onSelectRepo).toHaveBeenCalledWith('/workspace/backend');
  });
});
