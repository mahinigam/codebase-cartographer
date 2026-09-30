import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import Page from './page';

describe('Page', () => {
  it('renders without crashing', () => {
    const { container } = render(<Page />);
    expect(container).toBeTruthy();
  });
});
