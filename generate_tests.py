import os

tests = {
    "frontend/src/components/AskPanel.test.tsx": """import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { AskPanel } from './AskPanel';

describe('AskPanel', () => {
  it('renders nothing if no question/answer/loading', () => {
    const { container } = render(<AskPanel question="" answer="" semanticMatches={[]} loading={false} onSelectFile={()=>{}} onClear={()=>{}} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders loading state', () => {
    render(<AskPanel question="hello?" answer="" semanticMatches={[]} loading={true} onSelectFile={()=>{}} onClear={()=>{}} />);
    expect(screen.getByText('hello?')).toBeTruthy();
    expect(screen.getByText(/Analyzing architecture/i)).toBeTruthy();
  });

  it('renders answer and semantic matches', () => {
    const onSelectFile = vi.fn();
    const onClear = vi.fn();
    render(
      <AskPanel 
        question="what is this?" 
        answer="it is a test" 
        semanticMatches={[{ path: 'a.py', score: 0.9, summary: 'test file' }]} 
        loading={false} 
        onSelectFile={onSelectFile} 
        onClear={onClear} 
      />
    );
    expect(screen.getByText('it is a test')).toBeTruthy();
    expect(screen.getByText('a.py')).toBeTruthy();
    
    fireEvent.click(screen.getByText('Clear'));
    expect(onClear).toHaveBeenCalled();

    // The text 'a.py' is inside a div, but we can click the closest clickable item
    // Instead of clicking the text, we'll find the element and click it
    const item = screen.getByText('a.py').closest('.evidence-item');
    if (item) fireEvent.click(item);
    expect(onSelectFile).toHaveBeenCalledWith('a.py', 'ai');
  });
});
""",
    "frontend/src/components/CommandPalette.test.tsx": """import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { CommandPalette } from './CommandPalette';
import * as api from '../lib/api';

vi.mock('../lib/api', () => ({
  searchFiles: vi.fn(),
}));

describe('CommandPalette', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders and searches files', async () => {
    vi.mocked(api.searchFiles).mockResolvedValueOnce({
      results: [{ path: 'backend/search.py', score: 0.9, summary: 'Search logic' }]
    } as any);

    const onSelectFile = vi.fn();
    const onAsk = vi.fn();
    
    render(<CommandPalette isOpen={true} activeRepoPath="/repo" onClose={()=>{}} onSelectFile={onSelectFile} onAsk={onAsk} />);
    
    const input = screen.getByPlaceholderText(/Search files/i);
    fireEvent.change(input, { target: { value: 'search' } });
    
    await waitFor(() => {
      expect(screen.getByText('search.py')).toBeTruthy();
    });

    // Test ArrowDown and Enter
    fireEvent.keyDown(input, { key: 'ArrowDown' }); // selects Ask Cartographer
    fireEvent.keyDown(input, { key: 'ArrowDown' }); // selects search.py
    fireEvent.keyDown(input, { key: 'Enter' });
    
    expect(onSelectFile).toHaveBeenCalledWith('backend/search.py', 'search');
  });
  
  it('asks cartographer', async () => {
    const onAsk = vi.fn();
    render(<CommandPalette isOpen={true} activeRepoPath="/repo" onClose={()=>{}} onSelectFile={()=>{}} onAsk={onAsk} />);
    
    const input = screen.getByPlaceholderText(/Search files/i);
    fireEvent.change(input, { target: { value: 'what is this' } });
    
    await waitFor(() => {
      expect(screen.getByText(/Ask Cartographer:/)).toBeTruthy();
    });

    // Enter defaults to the first item which is "Ask cartographer"
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onAsk).toHaveBeenCalledWith('what is this');
  });
  
  it('closes on escape', () => {
    const onClose = vi.fn();
    render(<CommandPalette isOpen={true} activeRepoPath="/repo" onClose={onClose} onSelectFile={()=>{}} onAsk={()=>{}} />);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });
  
  it('shows suggested on empty input and can click them', () => {
    const onAsk = vi.fn();
    render(<CommandPalette isOpen={true} activeRepoPath="/repo" onClose={()=>{}} onSelectFile={()=>{}} onAsk={onAsk} />);
    
    const suggested = screen.getByText('Show the riskiest files');
    fireEvent.click(suggested);
    expect(onAsk).toHaveBeenCalledWith('Show the riskiest files');
  });
});
""",
    "frontend/src/app/CartographerApp.test.tsx": """import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import CartographerApp from './CartographerApp';
import * as api from '../lib/api';

vi.mock('../lib/api', () => ({
  listWorkspaces: vi.fn(),
  scanRepository: vi.fn(),
  getOverview: vi.fn(),
}));

// Mock matchMedia for UI components
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // Deprecated
    removeListener: vi.fn(), // Deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

describe('CartographerApp', () => {
  it('renders and fetches workspaces', async () => {
    vi.mocked(api.listWorkspaces).mockResolvedValueOnce([{ id: '1', root_path: '/test/repo', last_scanned: '2023-01-01' }] as any);
    vi.mocked(api.getOverview).mockResolvedValueOnce({
       overview: { files: 10, directories: 2, total_lines: 100, symbols: 5 },
       nodes: [],
       edges: [],
       file_metrics: []
    } as any);

    render(<CartographerApp />);
    
    // Should show the loading state of the graph or repo explorer
    await waitFor(() => {
      expect(screen.getByText(/\/test\/repo/)).toBeTruthy();
    });
  });
});
""",
    "frontend/src/components/GraphPanel.test.tsx": """import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { GraphPanel } from './GraphPanel';
import * as api from '../lib/api';

vi.mock('../lib/api', () => ({
  getOverview: vi.fn(),
}));

describe('GraphPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing', () => {
    const { container } = render(<GraphPanel activeRepoPath="/test" onSelectNode={()=>{}} />);
    expect(container).toBeTruthy();
  });
});
"""
}

for path, content in tests.items():
    with open(path, "w") as f:
        f.write(content)
        
print("Updated tests for coverage!")
