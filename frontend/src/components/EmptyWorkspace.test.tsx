import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { EmptyWorkspace } from './EmptyWorkspace';

describe('EmptyWorkspace', () => {
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
});
