import React from "react";
import { AlertTriangle, ChevronRight, File } from "lucide-react";

type Props = {
  files: Array<{ path: string; load_bearing_score: number }>;
  onSelectFile: (path: string) => void;
};

export function RiskHotspots({ files, onSelectFile }: Props) {
  const highRiskFiles = files
    .filter((f) => f.load_bearing_score > 75)
    .sort((a, b) => b.load_bearing_score - a.load_bearing_score);

  if (highRiskFiles.length === 0) {
    return (
      <div className="empty-state">
        <p>No high-risk hotspots identified.</p>
      </div>
    );
  }

  return (
    <div className="risk-hotspots-list">
      {highRiskFiles.map((f) => (
        <div key={f.path} className="hotspot-item clickable" onClick={() => onSelectFile(f.path)}>
          <AlertTriangle size={14} className="risk-icon" />
          <div className="hotspot-info">
            <span className="hotspot-name">{f.path.split("/").pop()}</span>
            <span className="hotspot-path">{f.path}</span>
          </div>
          <span className="hotspot-score">{Math.round(f.load_bearing_score)}</span>
        </div>
      ))}
    </div>
  );
}
