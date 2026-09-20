import React, { useState, useMemo } from "react";
import { ChevronRight, ChevronDown, Folder, File as FileIcon, Settings, RefreshCw, Layers, AlertTriangle, Clock } from "lucide-react";
import { RepositoryInfo } from "../lib/api";

type FileNode = {
  name: string;
  path: string;
  isDir: boolean;
  children?: FileNode[];
  loc?: number;
  score?: number;
};

type Props = {
  repositories: RepositoryInfo[];
  activeRepoPath: string;
  files: Array<{ path: string; loc: number; load_bearing_score: number }>;
  selectedFile: string | null;
  onSelectFile: (path: string) => void;
  onRepoChange: (path: string) => void;
  onRescan: () => void;
  onViewChange?: (view: "architecture" | "risk" | "recent") => void;
};

import { RiskHotspots } from "./RiskHotspots";

export function RepositoryExplorer({
  repositories,
  activeRepoPath,
  files,
  selectedFile,
  onSelectFile,
  onRepoChange,
  onRescan,
  onViewChange
}: Props) {
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set([""]));
  const [activeView, setActiveView] = useState<"architecture" | "risk">("architecture");

  const tree = useMemo(() => {
    const root: FileNode = { name: "root", path: "", isDir: true, children: [] };
    
    files.forEach(f => {
      const parts = f.path.split("/");
      let current = root;
      let currentPath = "";
      
      for (let i = 0; i < parts.length; i++) {
        const part = parts[i];
        currentPath = currentPath ? `${currentPath}/${part}` : part;
        const isDir = i < parts.length - 1;
        
        let child = current.children!.find(c => c.name === part);
        if (!child) {
          child = {
            name: part,
            path: currentPath,
            isDir,
            ...(isDir ? { children: [] } : { loc: f.loc, score: f.load_bearing_score })
          };
          current.children!.push(child);
        }
        current = child;
      }
    });

    // Sort: directories first, then alphabetically
    const sortTree = (node: FileNode) => {
      if (node.children) {
        node.children.sort((a, b) => {
          if (a.isDir && !b.isDir) return -1;
          if (!a.isDir && b.isDir) return 1;
          return a.name.localeCompare(b.name);
        });
        node.children.forEach(sortTree);
      }
    };
    sortTree(root);
    return root;
  }, [files]);

  const toggleFolder = (path: string) => {
    const next = new Set(expandedFolders);
    if (next.has(path)) {
      next.delete(path);
    } else {
      next.add(path);
    }
    setExpandedFolders(next);
  };

  const renderNode = (node: FileNode, depth: number) => {
    const isExpanded = expandedFolders.has(node.path);
    const isSelected = selectedFile === node.path;
    const paddingLeft = depth * 12 + 8;
    const isHighRisk = (node.score ?? 0) > 75;

    if (node.isDir) {
      return (
        <div key={node.path}>
          <div
            className={`tree-node dir-node ${isExpanded ? "expanded" : ""}`}
            style={{ paddingLeft }}
            onClick={() => toggleFolder(node.path)}
          >
            {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            <Folder size={14} className="folder-icon" />
            <span className="node-name">{node.name}</span>
          </div>
          {isExpanded && node.children?.map(c => renderNode(c, depth + 1))}
        </div>
      );
    }

    return (
      <div
        key={node.path}
        className={`tree-node file-node ${isSelected ? "selected" : ""}`}
        style={{ paddingLeft: paddingLeft + 18 }}
        onClick={() => onSelectFile(node.path)}
      >
        <FileIcon size={14} className="file-icon" />
        <span className="node-name">{node.name}</span>
        {isHighRisk && <div className="risk-indicator" title="High risk" />}
      </div>
    );
  };

  const activeRepo = repositories.find(r => r.root_path === activeRepoPath);

  return (
    <div className="repository-explorer">
      <div className="explorer-header">
        <div className="section-title">REPOSITORY</div>
        <select
          className="repo-selector"
          value={activeRepoPath}
          onChange={(e) => onRepoChange(e.target.value)}
        >
          <option value="" disabled>Select repository...</option>
          {repositories.map(r => (
            <option key={r.root_path} value={r.root_path}>{r.name}</option>
          ))}
        </select>
        {activeRepo && (
          <div className="repo-meta">
            {files.length} files • {activeRepo.indexed_at ? `indexed ${new Date(activeRepo.indexed_at).toLocaleTimeString()}` : 'indexed recently'}
            <button className="rescan-btn" onClick={onRescan} title="Rescan repository">
              <RefreshCw size={12} />
            </button>
          </div>
        )}
      </div>

      <div className="explorer-views">
        <div className="section-title">VIEWS</div>
        <button className={`view-btn ${activeView === "architecture" ? "active" : ""}`} onClick={() => { setActiveView("architecture"); onViewChange?.("architecture"); }}>
          <Layers size={14} /> Architecture
        </button>
        <button className={`view-btn ${activeView === "risk" ? "active" : ""}`} onClick={() => { setActiveView("risk"); onViewChange?.("risk"); }}>
          <AlertTriangle size={14} /> Risk hotspots
        </button>
      </div>

      <div className="explorer-tree">
        <div className="section-title">{activeView === "architecture" ? "FILES" : "HIGH RISK FILES"}</div>
        <div className="tree-container">
          {activeView === "architecture" ? (
            tree.children?.map(c => renderNode(c, 0))
          ) : (
            <RiskHotspots files={files} onSelectFile={onSelectFile} />
          )}
        </div>
      </div>
    </div>
  );
}
