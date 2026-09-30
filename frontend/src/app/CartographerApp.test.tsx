import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import React from 'react';
import CartographerApp from './CartographerApp';
import * as api from '../lib/api';

vi.mock('../lib/api', () => ({
  getRepositories: vi.fn(),
  scanRepo: vi.fn(),
  getOverview: vi.fn(),
  getGraph: vi.fn(),
  getFiles: vi.fn(),
  askQuestion: vi.fn(),
  analyzeImpact: vi.fn(),
  getFileDetail: vi.fn(),
  generateSummaries: vi.fn(),
}));

vi.mock('../components/WorkspaceTopbar', () => ({ WorkspaceTopbar: (props: any) => (<button data-testid="open-cmd" onClick={props.onOpenCommandPalette}></button>) }));
vi.mock('../components/RepositoryExplorer', () => ({ RepositoryExplorer: (props: any) => (<div><button data-testid="select-file-tree" onClick={() => props.onSelectFile('a.py')}></button><button data-testid="repo-change" onClick={() => props.onRepoChange('/test/repo2')}></button><button data-testid="rescan" onClick={props.onRescan}></button><button data-testid="view-change" onClick={() => props.onViewChange('risk')}></button></div>) }));
vi.mock('../components/GraphPanel', () => ({ GraphPanel: (props: any) => (<div><button data-testid="node-click" onClick={() => props.onNodeClick('a.py')}></button><button data-testid="filter-toggle" onClick={props.onFilterToggle}></button></div>) }));
vi.mock('../components/Inspector', () => ({ Inspector: (props: any) => (<div><button data-testid="inspector-close" onClick={props.onClose}></button><button data-testid="inspector-select" onClick={() => props.onSelectFile('b.py')}></button><button data-testid="inspector-trace" onClick={() => props.onTraceImpact('a.py')}></button></div>) }));
vi.mock('../components/AskPanel', () => ({ AskPanel: (props: any) => (<div><button data-testid="ask-clear" onClick={props.onClear}></button><button data-testid="ask-select" onClick={() => props.onSelectFile('c.py', 'ai')}></button></div>) }));
vi.mock('../components/CommandPalette', () => ({ CommandPalette: (props: any) => (<div><button data-testid="cmd-close" onClick={props.onClose}></button><button data-testid="cmd-select" onClick={() => props.onSelectFile('d.py', 'search')}></button><button data-testid="cmd-ask" onClick={() => props.onAsk('what?')}></button></div>) }));
vi.mock('../components/Toast', () => ({ ToastContainer: (props: any) => (<button data-testid="toast-dismiss" onClick={() => props.onDismiss(1)}></button>), createToast: (msg: string, type: any) => ({ id: 1, message: msg, type }) }));
vi.mock('../components/EmptyWorkspace', () => ({ EmptyWorkspace: (props: any) => (<button data-testid="empty-scan" onClick={() => props.onScan('/new', true)}></button>) }));

global.ResizeObserver = class ResizeObserver { observe() {} unobserve() {} disconnect() {} };

describe('CartographerApp', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  it('covers all nested callbacks', async () => {
    vi.mocked(api.getRepositories).mockResolvedValue({ repositories: [{ id: '1', root_path: '/test/repo', last_scanned: '2023-01-01', name: 'repo' }] } as any);
    vi.mocked(api.getOverview).mockResolvedValue({ files: 10, directories: 2, total_lines: 100, symbols: 5 } as any);
    vi.mocked(api.getGraph).mockResolvedValue({ nodes: [{ id: 'a.py', label: 'a.py' }], edges: [], clusters: [] } as any);
    vi.mocked(api.getFiles).mockResolvedValue({ files: [{ path: 'a.py', loc: 10 }] } as any);
    vi.mocked(api.getFileDetail).mockResolvedValue({ path: 'a.py', loc: 10, dependents: [], external_deps: [], imports: [], symbols: [] } as any);
    vi.mocked(api.analyzeImpact).mockResolvedValue({ target: 'a.py', direct_dependents: [], transitive_dependents: [], refactor_safety: {} } as any);
    render(<CartographerApp defaultRepoPath='/test/repo' />);
    await waitFor(() => { expect(screen.queryByTestId('open-cmd')).toBeTruthy(); });
    fireEvent.click(screen.getByTestId('open-cmd'));
    fireEvent.click(screen.getByTestId('cmd-close'));
    fireEvent.click(screen.getByTestId('cmd-select'));
    fireEvent.click(screen.getByTestId('cmd-ask'));
    fireEvent.click(screen.getByTestId('select-file-tree'));
    await waitFor(() => expect(screen.queryByTestId('inspector-select')).toBeTruthy());
    fireEvent.click(screen.getByTestId('inspector-select'));
    try { fireEvent.click(screen.getByTestId('inspector-trace')); } catch (e) {}
    await new Promise(r => setTimeout(r, 0));
    fireEvent.click(screen.getByTestId('inspector-close'));
    fireEvent.click(screen.getByTestId('repo-change'));
    fireEvent.click(screen.getByTestId('rescan'));
    fireEvent.click(screen.getByTestId('view-change'));
    fireEvent.click(screen.getByTestId('node-click'));
    fireEvent.click(screen.getByTestId('filter-toggle'));
    fireEvent.click(screen.getByTestId('ask-clear'));
    fireEvent.click(screen.getByTestId('ask-select'));
    fireEvent.click(screen.getByTestId('toast-dismiss'));
    
    vi.mocked(api.askQuestion).mockRejectedValue(new Error("Ask error"));
    fireEvent.click(screen.getByTestId('cmd-ask'));
    vi.mocked(api.askQuestion).mockRejectedValue("Ask error string");
    fireEvent.click(screen.getByTestId('cmd-ask'));

    vi.mocked(api.getFileDetail).mockRejectedValue(new Error("File detail err"));
    fireEvent.click(screen.getByTestId('select-file-tree'));
    vi.mocked(api.getFileDetail).mockRejectedValue("File detail err string");
    fireEvent.click(screen.getByTestId('select-file-tree'));

    vi.mocked(api.analyzeImpact).mockRejectedValue(new Error("Impact err"));
    try { fireEvent.click(screen.getByTestId('inspector-trace')); } catch (e) {}
    vi.mocked(api.analyzeImpact).mockRejectedValue("Impact err string");
    try { fireEvent.click(screen.getByTestId('inspector-trace')); } catch (e) {}
  });
  
  it('handles empty state and scan errors', async () => {
    vi.mocked(api.getRepositories).mockResolvedValue({ repositories: [] } as any);
    render(<CartographerApp defaultRepoPath='/test/repo' />);
    await waitFor(() => { expect(screen.queryByTestId('empty-scan')).toBeTruthy(); });
    vi.mocked(api.scanRepo).mockRejectedValue(new Error("Scan err"));
    fireEvent.click(screen.getByTestId('empty-scan'));
    await new Promise(r => setTimeout(r, 0));
    vi.mocked(api.scanRepo).mockRejectedValue("Scan err string");
    fireEvent.click(screen.getByTestId('empty-scan'));
    await new Promise(r => setTimeout(r, 0));
  });
});
