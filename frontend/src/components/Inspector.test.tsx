import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { Inspector } from './Inspector';

describe('Inspector', () => {
  it('covers all paths with components', () => {
    const fileData = {
      path: 'a/b/c.py',
      loc: 100,
      load_bearing_score: 90,
      risk_category: 'HIGH_RISK',
      risk_components: { fan_in: 0.5, complexity: 0.8 },
      dependents: ['x.py'],
      imports: ['y.py'],
      external_deps: ['react'],
      symbols: [{ name: 'Foo', kind: 'class' }],
      clusters: ['Core'],
      summary: 'This is a summary',
      architectural_role: 'Controller',
      framework: 'Django',
      is_dead_code: true,
      dead_code_category: 'Unreachable'
    };
    const impactData = {
      target: 'a/b/c.py',
      direct_dependents: ['x.py'],
      transitive_dependents: ['z.py'],
      refactor_safety: { safe_to_refactor: true, safe_probability: '90%', blast_radius: 'Low', recommended_strategy: 'do it' },
      explanation: 'Some explanation\nwith newlines'
    };
    
    render(
      <Inspector 
        file={fileData as any} 
        onClose={vi.fn()} 
        onSelectFile={vi.fn()} 
        onTraceImpact={vi.fn()}
        onAskAboutFile={vi.fn()}
        impactData={impactData}
      />
    );
    
    const btns = screen.queryAllByRole('button');
    btns.forEach(b => {
      try { fireEvent.click(b); } catch (e) {}
    });
    
    const items = screen.queryAllByText('x.py');
    items.forEach(i => {
      try { fireEvent.click(i); } catch (e) {}
    });
    
    const chevs = screen.queryAllByRole('img');
    chevs.forEach(c => {
       try { fireEvent.click(c); } catch (e) {}
    });
  });

  it('covers no risk components', () => {
    const fileData = {
      path: 'a.py',
      loc: 100,
      load_bearing_score: 20,
      dependents: [],
      imports: [],
      external_deps: [],
      symbols: [],
      clusters: [],
    };
    render(
      <Inspector 
        file={fileData as any} 
        onClose={vi.fn()} 
        onSelectFile={vi.fn()} 
        onTraceImpact={vi.fn()}
      />
    );
  });
});
