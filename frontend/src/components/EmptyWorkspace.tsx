import React, { useState } from "react";
import { FolderGit2, Map, Scan, Loader2 } from "lucide-react";

type Props = {
  defaultRepoPath: string;
  onScan: (path: string, summarize: boolean) => void;
  loading: boolean;
};

export function EmptyWorkspace({ defaultRepoPath, onScan, loading }: Props) {
  const [path, setPath] = useState(defaultRepoPath);
  const [summarize, setSummarize] = useState(true);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (path.trim()) {
      onScan(path.trim(), summarize);
    }
  };

  return (
    <div className="empty-workspace">
      <div className="empty-content">
        <div className="empty-icon">
          <Map size={48} />
        </div>
        <h1>Map your codebase</h1>
        <p className="subtitle">
          Turn a local repository into an interactive architecture map.
        </p>

        <form onSubmit={handleSubmit} className="scan-form">
          <div className="input-group">
            <FolderGit2 className="input-icon" size={18} />
            <input
              type="text"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="/Users/you/projects/my-app"
              disabled={loading}
              className="path-input"
            />
          </div>

          <div className="options-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={summarize}
                onChange={(e) => setSummarize(e.target.checked)}
                disabled={loading}
              />
              Generate AI summaries after scan
            </label>
          </div>

          <button type="submit" className="scan-submit-btn" disabled={loading || !path.trim()}>
            {loading ? (
              <>
                <Loader2 size={16} className="spin" /> Scanning repository...
              </>
            ) : (
              <>
                <Scan size={16} /> Analyze repository
              </>
            )}
          </button>
        </form>

        <div className="features-list">
          <span>Local-first indexing</span> • <span>dependency graph</span> • <span>risk analysis</span> • <span>AI explanations</span>
        </div>
      </div>
    </div>
  );
}
