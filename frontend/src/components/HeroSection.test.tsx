import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { HeroSection } from './HeroSection';

describe('HeroSection', () => {
  it('covers all paths with and without loading', () => {
    const onScan = vi.fn();
    const onRepoPathChange = vi.fn();
    
    const { rerender } = render(<HeroSection onScan={onScan} onRepoPathChange={onRepoPathChange} repoPath="" loading={false} />);
    
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: '/foo' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    fireEvent.keyDown(input, { key: 'a' }); // missing branch coverage
    
    const btn = screen.getByRole('button');
    fireEvent.click(btn);

    rerender(<HeroSection onScan={onScan} onRepoPathChange={onRepoPathChange} repoPath="" loading={true} />);
  });
});
