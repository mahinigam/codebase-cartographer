import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { RepoBand } from './RepoBand';

describe('RepoBand', () => {
  it('covers all paths', () => {
    const onRepoChange = vi.fn();
    const onSummarizeOnScanChange = vi.fn();
    const onGenerateSummaries = vi.fn();
    const repos = [{ root_path: '/a', name: 'A', files: 1 }, { root_path: '/b', name: 'B', files: 2 }];
    
    render(<RepoBand activeRepoPath="/a" repositories={repos as any} summarizeOnScan={false} onRepoChange={onRepoChange} onSummarizeOnScanChange={onSummarizeOnScanChange} onGenerateSummaries={onGenerateSummaries} loadingSummaries={false} />);
    
    const select = screen.getByRole('combobox');
    fireEvent.change(select, { target: { value: '/b' } });
    
    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);
    
    const btn = screen.getByRole('button');
    fireEvent.click(btn);
  });
});
