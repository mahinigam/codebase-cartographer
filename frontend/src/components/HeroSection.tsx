import { Radar } from "lucide-react";
import { Spinner } from "./Spinner";

type Props = {
  repoPath: string;
  onRepoPathChange: (path: string) => void;
  onScan: () => void;
  loading: boolean;
};

export function HeroSection({
  repoPath,
  onRepoPathChange,
  onScan,
  loading,
}: Props) {
  return (
    <section className="hero">
      <div>
        <p className="eyebrow">Index Workspace</p>
      </div>
      <div className="scanBar">
        <input
          id="repo-path-input"
          value={repoPath}
          onChange={(e) => onRepoPathChange(e.target.value)}
          placeholder="Paste a local repository path…"
          onKeyDown={(e) => {
            if (e.key === "Enter") onScan();
          }}
        />
        <button id="analyze-button" onClick={onScan} disabled={loading}>
          {loading ? <Spinner /> : <Radar size={18} />}
          {loading ? "Scanning…" : "Analyze"}
        </button>
      </div>
    </section>
  );
}
