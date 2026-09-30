import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { LoadBearingFiles } from './LoadBearingFiles';

describe('LoadBearingFiles', () => {
  it('covers all paths with empty array', () => {
    const onFileClick = vi.fn();
    const { rerender } = render(<LoadBearingFiles files={[]} onFileClick={onFileClick} />);
    
    const files = [{ path: 'a.py', load_bearing_score: 90, risk_category: 'HIGH_RISK', risk_components: {} }];
    rerender(<LoadBearingFiles files={files as any} onFileClick={onFileClick} />);
  });
});
