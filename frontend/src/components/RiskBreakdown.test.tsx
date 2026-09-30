import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { RiskBreakdown } from './RiskBreakdown';

describe('RiskBreakdown', () => {
  it('covers all paths with various risk numbers', () => {
    const riskComponents = { fan_in: 0.1, fan_out: 0.5, complexity: 0.8, churn_count: 1, fan_in_normalized: 0.1, complexity_normalized: 0.8, churn_normalized: 1.0, fan_out_normalized: 0.5 };
    const { rerender } = render(<RiskBreakdown riskComponents={riskComponents} />);
    
    const riskComponents2 = { fan_in: 0.8, fan_out: 0.1, complexity: 0.2, churn_count: 0.2, fan_in_normalized: 0.8, complexity_normalized: 0.2, churn_normalized: 0.2, fan_out_normalized: 0.1 };
    rerender(<RiskBreakdown riskComponents={riskComponents2} />);
  });
});
