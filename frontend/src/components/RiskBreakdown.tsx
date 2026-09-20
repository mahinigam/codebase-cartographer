import React from "react";
import { FileDetail } from "../lib/api";

export function RiskBreakdown({ riskComponents }: { riskComponents: NonNullable<FileDetail["risk_components"]> }) {
  const bars = [
    { label: "Fan-in", value: riskComponents.fan_in, norm: riskComponents.fan_in_normalized },
    { label: "Complexity", value: riskComponents.complexity, norm: riskComponents.complexity_normalized },
    { label: "Churn", value: riskComponents.churn_count, norm: riskComponents.churn_normalized },
    { label: "Fan-out", value: riskComponents.fan_out, norm: riskComponents.fan_out_normalized },
  ];

  return (
    <div className="risk-breakdown">
      {bars.map((b) => (
        <div key={b.label} className="risk-bar-row">
          <div className="risk-bar-label">
            <span>{b.label}</span>
            <span className="risk-bar-value">{b.value}</span>
          </div>
          <div className="risk-bar-track">
            <div
              className={`risk-bar-fill ${b.norm > 0.75 ? "high" : b.norm > 0.5 ? "medium" : "low"}`}
              style={{ width: `${Math.max(b.norm * 100, 2)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
