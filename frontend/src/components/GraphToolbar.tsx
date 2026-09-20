import React from "react";
import { Filter, ZoomIn, ZoomOut, Maximize, Activity } from "lucide-react";
import { Overview } from "../lib/api";

type Props = {
  overview: Overview["overview"];
  totalFiles: number;
  totalEdges: number;
  avgRisk: number;
  onFit: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFilterToggle: () => void;
};

export function GraphToolbar({
  overview,
  totalFiles,
  totalEdges,
  avgRisk,
  onFit,
  onZoomIn,
  onZoomOut,
  onFilterToggle
}: Props) {
  return (
    <div className="graph-toolbar">
      <div className="status-strip">
        <Activity size={12} className="status-icon" />
        <span>{totalFiles} files</span>
        <span className="separator">·</span>
        <span>{totalEdges} edges</span>
        {overview.symbols !== undefined && (
          <>
            <span className="separator">·</span>
            <span>{overview.symbols} symbols</span>
          </>
        )}
        <span className="separator">·</span>
        <span className="risk-avg">avg risk {avgRisk}</span>
      </div>
      
      <div className="toolbar-controls">
        <button className="control-btn" onClick={onFilterToggle} title="Filters">
          <Filter size={14} /> Filters
        </button>
        <div className="divider"></div>
        <button className="control-btn" onClick={onFit} title="Fit to view">
          <Maximize size={14} />
        </button>
        <button className="control-btn" onClick={onZoomOut} title="Zoom out">
          <ZoomOut size={14} />
        </button>
        <button className="control-btn" onClick={onZoomIn} title="Zoom in">
          <ZoomIn size={14} />
        </button>
      </div>
    </div>
  );
}
