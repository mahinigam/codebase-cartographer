import React from 'react';
import { render, screen } from '@testing-library/react';
import { Inspector } from './Inspector';
import { describe, it, expect, vi } from 'vitest';
import '@testing-library/jest-dom';

describe('Inspector Component', () => {
  const mockFile = {
    path: '/src/index.ts',
    language: 'typescript',
    loc: 100,
    dependents: ['a', 'b'],
    imports: ['c'],
    complexity: 10,
    load_bearing_score: 80, // High risk
    risk_category: 'SINGLE_POINT_OF_FAILURE',
    architectural_role: 'CORE_ORCHESTRATOR',
    framework: 'React',
    is_test_file: false,
    is_dead_code: true,
    dead_code_category: 'UNUSED_EXPORT',
    symbols: [],
    external_deps: [],
    summary: 'A core file'
  };

  it('renders Inspector with proper Jev risk categories and architectural roles', () => {
    const handleClose = vi.fn();
    const handleSelectFile = vi.fn();
    const handleTraceImpact = vi.fn();

    render(
      <Inspector 
        file={mockFile as any}
        onClose={handleClose}
        onSelectFile={handleSelectFile}
        onTraceImpact={handleTraceImpact}
      />
    );

    // Verify filename
    expect(screen.getByText('index.ts')).toBeInTheDocument();
    
    // Verify Risk Badge
    expect(screen.getByText('Risk 80')).toBeInTheDocument();
    
    // Verify Jev Category
    expect(screen.getByText('Jev Category: SINGLE POINT OF FAILURE')).toBeInTheDocument();
    
    // Verify Role
    expect(screen.getByText('Role: CORE_ORCHESTRATOR')).toBeInTheDocument();

    // Verify Framework
    expect(screen.getByText('Framework: React')).toBeInTheDocument();

    // Verify Dead Code Warning
    expect(screen.getByText(/LIKELY DEAD CODE/)).toBeInTheDocument();
    expect(screen.getByText(/UNUSED_EXPORT/)).toBeInTheDocument();
  });
});
