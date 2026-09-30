import React from 'react';
import { render } from '@testing-library/react';
import { GraphPanel } from './GraphPanel';
import { describe, it, expect, vi } from 'vitest';
import '@testing-library/jest-dom';

// Mock reactflow to avoid JS DOM issues with ResizeObserver
vi.mock('reactflow', async () => {
  const actual = await vi.importActual('reactflow');
  return {
    ...actual as any,
    default: ({ children }: any) => <div data-testid="reactflow-mock">{children}</div>,
    ReactFlowProvider: ({ children }: any) => <div>{children}</div>,
    Background: () => <div />,
    MiniMap: () => <div />,
    Handle: () => <div />,
    useReactFlow: () => ({ fitView: vi.fn(), zoomIn: vi.fn(), zoomOut: vi.fn() })
  };
});

// We can just verify it doesn't crash given graph data, 
// and test the scope buttons
describe('GraphPanel Component', () => {
  const mockGraph = {
    nodes: [
      { id: '1', label: '/src/a.ts', score: 90, is_test_file: false, labels: [] },
      { id: '2', label: '/src/a.test.ts', score: 20, is_test_file: true, labels: [] }
    ],
    edges: [],
    clusters: [
      { name: 'Core', files: 2, avg_score: 55, max_score: 90, cohesion: 0.8, coupling: 0.2, extraction_readiness: 'HIGH' }
    ]
  };

  it('renders architecture scope and handles graph layout', () => {
    const handleNodeClick = vi.fn();
    
    const { getByText, getByTestId } = render(
      <GraphPanel 
        graph={mockGraph}
        onNodeClick={handleNodeClick}
      />
    );

    // Verify Scope Label
    expect(getByText('ARCHITECTURE SCOPE')).toBeInTheDocument();
    
    // Verify Cluster button
    expect(getByText('Core')).toBeInTheDocument();
    
    // Verify ReactFlow is mocked and rendered
    expect(getByTestId('reactflow-mock')).toBeInTheDocument();
  });
});
