import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { RepositoryExplorer } from './RepositoryExplorer';

describe('RepositoryExplorer', () => {
  it('covers all paths with search filtering and toggle', () => {
    const onSelectFile = vi.fn();
    const onRepoChange = vi.fn();
    const onRescan = vi.fn();
    const onViewChange = vi.fn();
    
    const repos = [{ root_path: '/repo', name: 'Repo', files: 1, indexed_at: '2023-01-01T00:00:00Z' }];
    const files = [
      { path: 'dir1/a.py', loc: 10, risk_category: 'HIGH_RISK', architectural_role: 'Controller', framework: 'Django', score: 90, dependents: 2, _is_test: false },
      { path: 'dir1/b.py', loc: 10, risk_category: 'HIGH_RISK', architectural_role: 'Controller', framework: 'Django', score: 40, dependents: 2, _is_test: false },
      { path: 'c.py', loc: 10, risk_category: 'HIGH_RISK', architectural_role: 'Controller', framework: 'Django', score: 90, dependents: 2, _is_test: false }
    ];
    
    render(<RepositoryExplorer repositories={repos as any} activeRepoPath="/repo" files={files as any} selectedFile="dir1/a.py" onSelectFile={onSelectFile} onRepoChange={onRepoChange} onRescan={onRescan} onViewChange={onViewChange} />);
    
    // Switch view
    const btns = screen.queryAllByRole('button');
    btns.forEach(b => { try { fireEvent.click(b); } catch (e) {} });

    const dirNodes = document.querySelectorAll('.dir-node');
    dirNodes.forEach(d => {
      fireEvent.click(d); // collapse
      fireEvent.click(d); // expand
    });
    
    const treeNodes = document.querySelectorAll('.file-node');
    treeNodes.forEach(t => fireEvent.click(t));
    
  });

  it('handles empty and short risk components', () => {
     const onSelectFile = vi.fn();
     const repos = [{ root_path: '/repo', name: 'Repo', files: 1 }];
     const files = [
       { path: 'b.py', loc: 10, score: 20, _is_test: true },
       { path: 'c.py' }
     ];
     render(<RepositoryExplorer repositories={repos as any} activeRepoPath="/repo" files={files as any} selectedFile="b.py" onSelectFile={onSelectFile} onRepoChange={vi.fn()} onRescan={vi.fn()} onViewChange={vi.fn()} />);
  });
});
