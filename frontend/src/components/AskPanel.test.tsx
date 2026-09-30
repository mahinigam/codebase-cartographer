import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { AskPanel } from './AskPanel';

describe('AskPanel', () => {
  it('renders nothing if no question/answer/loading', () => {
    const { container } = render(<AskPanel question="" answer="" semanticMatches={[]} loading={false} onSelectFile={()=>{}} onClear={()=>{}} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders loading state', () => {
    render(<AskPanel question="hello?" answer="" semanticMatches={[]} loading={true} onSelectFile={()=>{}} onClear={()=>{}} />);
    expect(screen.getByText('hello?')).toBeTruthy();
    expect(screen.getByText(/Analyzing architecture/i)).toBeTruthy();
  });

  it('renders answer and semantic matches', () => {
    const onSelectFile = vi.fn();
    const onClear = vi.fn();
    render(
      <AskPanel 
        question="what is this?" 
        answer="it is a test" 
        semanticMatches={[{ path: 'a.py', score: 0.9, summary: 'test file' }]} 
        loading={false} 
        onSelectFile={onSelectFile} 
        onClear={onClear} 
      />
    );
    expect(screen.getByText('it is a test')).toBeTruthy();
    expect(screen.getByText('a.py')).toBeTruthy();
    
    fireEvent.click(screen.getByText('Clear'));
    expect(onClear).toHaveBeenCalled();

    // The text 'a.py' is inside a div, but we can click the closest clickable item
    // Instead of clicking the text, we'll find the element and click it
    const item = screen.getByText('a.py').closest('.evidence-item');
    if (item) fireEvent.click(item);
    expect(onSelectFile).toHaveBeenCalledWith('a.py', 'ai');
  });
});
