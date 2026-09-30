import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { GraphToolbar } from './GraphToolbar';

describe('GraphToolbar', () => {
  it('renders and interacts', () => {
    const overview = { files: 10, directories: 2, total_lines: 100, symbols: 5 };
    const filters = { hideTests: false, highRiskOnly: false, hideIsolated: false };
    const onFilterChange = vi.fn();
    const onFilterToggle = vi.fn();
    
    render(
      <GraphToolbar 
        overview={overview as any} 
        totalFiles={10} 
        totalEdges={20} 
        avgRisk={5.5} 
        onFit={()=>{}} 
        onZoomIn={()=>{}} 
        onZoomOut={()=>{}} 
        onFilterToggle={onFilterToggle}
        isFilterOpen={true}
        filters={filters}
        onFilterChange={onFilterChange}
      />
    );
    
    expect(screen.getByText(/10 files/)).toBeTruthy();
    expect(screen.getByText(/5 symbols/)).toBeTruthy();
    
    const checkbox = screen.getByLabelText(/Hide Test Files/i);
    fireEvent.click(checkbox);
    expect(onFilterChange).toHaveBeenCalledWith({ ...filters, hideTests: true });

    const checkbox2 = screen.getByLabelText(/High Risk Only/i);
    fireEvent.click(checkbox2);
    expect(onFilterChange).toHaveBeenCalledWith({ ...filters, highRiskOnly: true });

    const checkbox3 = screen.getByLabelText(/Hide Isolated Nodes/i);
    fireEvent.click(checkbox3);
    expect(onFilterChange).toHaveBeenCalledWith({ ...filters, hideIsolated: true });
    
    const filterBtn = screen.getByTitle('Filters');
    fireEvent.click(filterBtn);
    expect(onFilterToggle).toHaveBeenCalled();
  });
});
