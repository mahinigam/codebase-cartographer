import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { ImpactPanel } from './ImpactPanel';

describe('ImpactPanel', () => {
  it('covers all paths with and without loading', () => {
    const onSelectedFileChange = vi.fn();
    const onTrace = vi.fn();
    const { rerender } = render(<ImpactPanel selectedFile="a.py" onSelectedFileChange={onSelectedFileChange} onTrace={onTrace} impact="High" loading={false} />);
    
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'b.py' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    
    const btn = screen.getByRole('button');
    fireEvent.click(btn);

    rerender(<ImpactPanel selectedFile="a.py" onSelectedFileChange={onSelectedFileChange} onTrace={onTrace} impact="High" loading={true} />);
    rerender(<ImpactPanel selectedFile="" onSelectedFileChange={onSelectedFileChange} onTrace={onTrace} impact="" loading={false} />);
  });
});
