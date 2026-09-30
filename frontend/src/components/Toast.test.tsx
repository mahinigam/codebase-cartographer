import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import React from 'react';
import { ToastContainer, createToast } from './Toast';

describe('Toast', () => {
  it('renders and auto dismisses toasts', async () => {
    vi.useFakeTimers();
    const onDismiss = vi.fn();
    const t = createToast('Success message', 'success');
    
    render(
      <ToastContainer toasts={[t]} onDismiss={onDismiss} />
    );
    
    expect(screen.getByText('Success message')).toBeTruthy();
    
    // Fast forward for auto dismissal (6000ms in ToastCard)
    act(() => {
      vi.advanceTimersByTime(6000);
    });
    
    expect(onDismiss).toHaveBeenCalledWith(t.id);
    vi.useRealTimers();
  });
  
  it('dismisses toast on click', async () => {
    const onDismiss = vi.fn();
    const t = createToast('Error message', 'error');
    
    render(
      <ToastContainer toasts={[t]} onDismiss={onDismiss} />
    );
    
    const closeBtn = screen.getByRole('button', { name: /Dismiss/i });
    fireEvent.click(closeBtn);
    
    expect(onDismiss).toHaveBeenCalledWith(t.id);
  });
});
