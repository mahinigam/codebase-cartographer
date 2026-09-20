import React from "react";
import { Filter, ZoomIn, ZoomOut, Maximize, Activity } from "lucide-react";
import { Overview } from "../lib/api";

export type GraphFilters = {
  hideTests: boolean;
  highRiskOnly: boolean;
  hideIsolated: boolean;
};

type Props = {
  overview: Overview["overview"];
  totalFiles: number;
  totalEdges: number;
  avgRisk: number;
  onFit: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFilterToggle: () => void;
  isFilterOpen?: boolean;
  filters?: GraphFilters;
  onFilterChange?: (filters: GraphFilters) => void;
};

export function GraphToolbar({
  overview,
  totalFiles,
  totalEdges,
  avgRisk,
  onFit,
  onZoomIn,
  onZoomOut,
  onFilterToggle,
  isFilterOpen,
  filters,
  onFilterChange
}: Props) {
  return (
    <div className="graph-toolbar">
      {isFilterOpen && filters && onFilterChange && (
        <div className="filter-dropdown">
          <div className="filter-header">Graph Filters</div>
          <label className="filter-option">
            <input 
              type="checkbox" 
              checked={filters.hideTests} 
              onChange={(e) => onFilterChange({ ...filters, hideTests: e.target.checked })}
            />
            <span>Hide Test Files</span>
          </label>
          <label className="filter-option">
            <input 
              type="checkbox" 
              checked={filters.highRiskOnly} 
              onChange={(e) => onFilterChange({ ...filters, highRiskOnly: e.target.checked })}
            />
            <span>High Risk Only (&gt; 75)</span>
          </label>
          <label className="filter-option">
            <input 
              type="checkbox" 
              checked={filters.hideIsolated} 
              onChange={(e) => onFilterChange({ ...filters, hideIsolated: e.target.checked })}
            />
            <span>Hide Isolated Nodes</span>
          </label>
        </div>
      )}

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
        <button className={`control-btn ${isFilterOpen ? "active" : ""}`} onClick={onFilterToggle} title="Filters">
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
