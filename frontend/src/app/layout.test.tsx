import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import RootLayout from './layout';

describe('RootLayout', () => {
  it('renders children correctly', () => {
    const { container } = render(
      <RootLayout>
        <div data-testid="child">Test Child</div>
      </RootLayout>
    );
    expect(container.querySelector('[data-testid="child"]')).toBeTruthy();
  });
});
