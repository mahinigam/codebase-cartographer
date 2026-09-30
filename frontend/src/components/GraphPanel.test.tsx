import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { GraphPanel } from './GraphPanel';
import { ReactFlowProvider, useReactFlow } from 'reactflow';

global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

describe('GraphPanel', () => {
  const graph = {
    nodes: [
      { id: 'a.py', label: 'a.py', score: 80, labels: [], language: 'Python', loc: 100, fan_in: 2, is_test_file: false, framework: 'Django', is_dead_code: true },
      { id: 'b.py', label: 'b.py', score: 20, labels: [], is_test_file: true },
      { id: 'c.py', label: 'c.py', score: 50, labels: [], is_test_file: false }
    ],
    edges: [
      { source: 'a.py', target: 'b.py', type: 'import' }
    ],
    clusters: [
      { name: 'Core', files: 10, avg_score: 90, max_score: 100, cohesion: 0.8, coupling: 0.2, extraction_readiness: 'High' },
      { name: 'Other', files: 5, avg_score: 20, max_score: 40 }
    ]
  };
  const overview = { avg_score: 50 };
  
  it('renders clusters and high risk nodes', () => {
    const onNodeClick = vi.fn();
    render(<GraphPanel graph={graph} onNodeClick={onNodeClick} overview={overview} selectedFile="a.py" />);
    
    expect(screen.getByText('Core')).toBeTruthy();
  });

  it('handles impact mode', () => {
    const onNodeClick = vi.fn();
    const impactData = { target: 'a.py', direct_dependents: ['b.py'], transitive_dependents: [{path: 'c.py'}] };
    render(<GraphPanel graph={graph} onNodeClick={onNodeClick} overview={overview} impactMode={true} impactData={impactData} />);
  });

  it('handles empty graph', () => {
    const onNodeClick = vi.fn();
    render(<GraphPanel graph={{nodes: [], edges: [], clusters: []}} onNodeClick={onNodeClick} />);
  });

  it('handles filters and missing overview', async () => {
    const onNodeClick = vi.fn();
    render(<GraphPanel graph={graph} onNodeClick={onNodeClick} overview={overview} />);
    
    const filterBtn = screen.getByRole('button', { name: /Filters/i });
    fireEvent.click(filterBtn);
    
    const testFilter = screen.getByRole('checkbox', { name: /Hide Test Files/i });
    fireEvent.click(testFilter);
    
    const riskFilter = screen.getByRole('checkbox', { name: /High Risk Only/i });
    fireEvent.click(riskFilter);

    const isolatedFilter = screen.getByRole('checkbox', { name: /Hide Isolated Nodes/i });
    fireEvent.click(isolatedFilter);
    
    const fitBtn = screen.getByTitle('Fit to view');
    fireEvent.click(fitBtn);
    
    const zIn = screen.getByTitle('Zoom in');
    fireEvent.click(zIn);
    
    const zOut = screen.getByTitle('Zoom out');
    fireEvent.click(zOut);
  });
});
