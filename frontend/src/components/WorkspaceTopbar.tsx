import React from "react";
import { Home } from "lucide-react";

type Props = {
  repoName: string;
  branch?: string;
  onOpenCommandPalette: () => void;
  onHome?: () => void;
};

export function WorkspaceTopbar({ repoName, branch, onOpenCommandPalette, onHome }: Props) {
  return (
    <header className="workspace-topbar">
      <div className="topbar-left">
        {onHome && (
          <button className="home-button" onClick={onHome} aria-label="Home" style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', display: 'flex', alignItems: 'center', padding: '0 8px' }}>
            <Home size={18} />
          </button>
        )}
        <span className="brand">Cartographer</span>
        <span className="divider">/</span>
        <span className="repo-name">{repoName || "No repository selected"}</span>
        {branch && <span className="branch-name">{branch}</span>}
      </div>
      
      <div className="topbar-center">
        <button className="command-palette-trigger" onClick={onOpenCommandPalette}>
          <span className="icon">⌕</span>
          <span className="text">Search files, symbols, or ask Cartographer...</span>
          <span className="shortcut">⌘K</span>
        </button>
      </div>
      
      <div className="topbar-right">
        {/* Status indicator can go here */}
      </div>
    </header>
  );
}
