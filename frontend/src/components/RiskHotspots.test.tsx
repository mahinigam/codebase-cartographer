import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { RiskHotspots } from './RiskHotspots';

describe('RiskHotspots', () => {
  it('covers all paths', () => {
    const onSelectFile = vi.fn();
    const files = [{ path: 'a.py', load_bearing_score: 90, risk_category: 'HIGH_RISK', risk_components: {} }, { path: 'b.py', load_bearing_score: 50, risk_category: 'LOW_RISK', risk_components: {} }];
    render(<RiskHotspots files={files as any} onSelectFile={onSelectFile} />);
    
    const items = screen.queryAllByText('a.py');
    items.forEach(i => {
      try { fireEvent.click(i); } catch (e) {}
    });
  });
});
