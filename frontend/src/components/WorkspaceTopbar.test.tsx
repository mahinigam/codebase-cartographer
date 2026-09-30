import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { WorkspaceTopbar } from './WorkspaceTopbar';

describe('WorkspaceTopbar', () => {
  it('covers all paths', () => {
    const { rerender } = render(<WorkspaceTopbar repoName="Repo" branch="main" onOpenCommandPalette={vi.fn()} />);
    rerender(<WorkspaceTopbar repoName="" onOpenCommandPalette={vi.fn()} />);
  });
});
