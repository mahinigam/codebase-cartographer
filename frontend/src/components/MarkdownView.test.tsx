import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { MarkdownView } from './MarkdownView';

describe('MarkdownView', () => {
  it('renders without crashing', () => {
    // Basic render test to ensure component mounts
    const { container } = render(<MarkdownView files={[]} repositories={[]} toasts={[]} riskComponents={{}} node={{ id: "1" }} markdown="" impact={{}} summary={{}} {...({} as any)} />);
    expect(container).toBeTruthy();
  });
});

