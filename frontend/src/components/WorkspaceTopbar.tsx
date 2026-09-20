import React from "react";

type Props = {
  repoName: string;
  branch?: string;
  onOpenCommandPalette: () => void;
};

export function WorkspaceTopbar({ repoName, branch, onOpenCommandPalette }: Props) {
  return (
    <header className="workspace-topbar">
      <div className="topbar-left">
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
