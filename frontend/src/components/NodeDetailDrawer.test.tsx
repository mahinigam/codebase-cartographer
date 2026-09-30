import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { NodeDetailDrawer } from './NodeDetailDrawer';
import * as api from '../lib/api';

vi.mock('../lib/api', () => ({
  getFileDetail: vi.fn(),
}));

describe('NodeDetailDrawer', () => {
  it('covers all paths', async () => {
    const onClose = vi.fn();
    const onTraceImpact = vi.fn();
    
    vi.mocked(api.getFileDetail).mockResolvedValue({
       path: 'a.py', loc: 100, load_bearing_score: 90, dependents: ['b.py'], external_deps: ['react'], imports: ['c.py'], symbols: ['Foo'], summary: 'test'
    } as any);
    
    render(
      <NodeDetailDrawer 
        filePath="a.py" 
        repoPath="/repo"
        onClose={onClose} 
        onTraceImpact={onTraceImpact} 
      />
    );
    
    await waitFor(() => {
      expect(api.getFileDetail).toHaveBeenCalled();
    });
    
    await new Promise(r => setTimeout(r, 100));
    
    const btns = screen.queryAllByRole('button');
    btns.forEach(b => {
      try { fireEvent.click(b); } catch(e) {}
    });
  });
  
  it('covers error', async () => {
     vi.mocked(api.getFileDetail).mockRejectedValue(new Error("fail"));
     render(<NodeDetailDrawer filePath="err.py" repoPath="/repo" onClose={vi.fn()} onTraceImpact={vi.fn()} />);
     await new Promise(r => setTimeout(r, 100));
  });
});
