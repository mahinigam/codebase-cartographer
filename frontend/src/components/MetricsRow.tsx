import React from "react";
import { Activity, GitBranch, Layers3, ShieldAlert } from "lucide-react";

type OverviewData = {
  files: number;
  symbols: number;
  avg_score: number;
};

type Props = {
  overview: OverviewData;
  riskyFileCount: number;
};

function Metric({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
}) {
  return (
    <div className="metric">
      {icon}
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function MetricsRow({ overview, riskyFileCount }: Props) {
  return (
    <section className="metrics">
      <Metric icon={<Layers3 />} label="Files" value={overview.files} />
      <Metric icon={<GitBranch />} label="Symbols" value={overview.symbols} />
      <Metric
        icon={<Activity />}
        label="Avg Risk"
        value={overview.avg_score}
      />
      <Metric
        icon={<ShieldAlert />}
        label="Load-Bearing"
        value={riskyFileCount}
      />
    </section>
  );
}
