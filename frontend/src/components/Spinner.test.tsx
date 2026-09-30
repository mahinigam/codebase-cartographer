import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Spinner } from './Spinner';

describe('Spinner', () => {
  it('renders without crashing', () => {
    // Basic render test to ensure component mounts
    const { container } = render(<Spinner files={[]} repositories={[]} toasts={[]} riskComponents={{}} node={{ id: "1" }} markdown="" impact={{}} summary={{}} {...({} as any)} />);
    expect(container).toBeTruthy();
  });
});

