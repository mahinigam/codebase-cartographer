import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as api from './api';

describe('API Functions', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() => 
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ data: 'mocked' })
      })
    ));
    vi.stubGlobal('process', {
      env: { NEXT_PUBLIC_API_BASE: '', NEXT_PUBLIC_API_TOKEN: 'token' }
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('scanRepo', async () => {
    const res = await api.scanRepo('test_repo', true, false);
    expect(res).toEqual({ data: 'mocked' });
  });

  it('getRepositories', async () => {
    const res = await api.getRepositories();
    expect(res).toEqual({ data: 'mocked' });
  });

  it('getFiles', async () => {
    const res = await api.getFiles('repo');
    expect(res).toEqual({ data: 'mocked' });
  });

  it('getOverview', async () => {
    const res = await api.getOverview('repo');
    expect(res).toEqual({ data: 'mocked' });
  });

  it('getGraph', async () => {
    const res = await api.getGraph('repo', 10, 'prefix');
    expect(res).toEqual({ data: 'mocked' });
  });

  it('askQuestion', async () => {
    const res = await api.askQuestion('q', 'repo');
    expect(res).toEqual({ data: 'mocked' });
  });

  it('searchFiles', async () => {
    const res = await api.searchFiles('query', 'repo');
    expect(res).toEqual({ data: 'mocked' });
  });

  it('analyzeImpact', async () => {
    const res = await api.analyzeImpact('path', 2, 'repo');
    expect(res).toEqual({ data: 'mocked' });
  });

  it('getFileDetail', async () => {
    const res = await api.getFileDetail('path', 'repo');
    expect(res).toEqual({ data: 'mocked' });
  });

  it('generateSummaries', async () => {
    const res = await api.generateSummaries('repo', 5);
    expect(res).toEqual({ data: 'mocked' });
  });

  it('withQuery ignores undefined and empty string', () => {
    expect(api.withQuery('/path', { a: 1, b: undefined, c: '' })).toBe('/path?a=1');
  });

  it('handles fetch errors', async () => {
    vi.stubGlobal('fetch', vi.fn(() => 
      Promise.resolve({
        ok: false,
        statusText: 'Not Found',
        text: () => Promise.resolve('Error Not Found')
      })
    ));
    await expect(api.getRepositories()).rejects.toThrow('Error Not Found');
  });
});
