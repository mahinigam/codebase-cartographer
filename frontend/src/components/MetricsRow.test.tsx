import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { MetricsRow } from './MetricsRow';

describe('MetricsRow', () => {
  it('renders metrics correctly', () => {
    const overview = { files: 100, symbols: 300, avg_score: 55 };
    render(<MetricsRow overview={overview as any} riskyFileCount={12} />);
    expect(screen.getByText('100')).toBeTruthy(); // files
    expect(screen.getByText('300')).toBeTruthy(); // symbols
    expect(screen.getByText('12')).toBeTruthy(); // load-bearing
  });
});
