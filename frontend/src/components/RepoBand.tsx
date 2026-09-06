import { RepositoryInfo } from "../lib/api";
import { Spinner } from "./Spinner";

type Props = {
  activeRepoPath: string;
  repositories: RepositoryInfo[];
  summarizeOnScan: boolean;
  onRepoChange: (path: string) => void;
  onSummarizeOnScanChange: (checked: boolean) => void;
  onGenerateSummaries: () => void;
  loadingSummaries: boolean;
};

export function RepoBand({
  activeRepoPath,
  repositories,
  summarizeOnScan,
  onRepoChange,
  onSummarizeOnScanChange,
  onGenerateSummaries,
  loadingSummaries,
}: Props) {
  return (
    <section className="repoBand">
      <label>
        Active repo
        <select
          id="repo-selector"
          value={activeRepoPath}
          onChange={(e) => onRepoChange(e.target.value)}
        >
          <option value={activeRepoPath}>{activeRepoPath || "—"}</option>
          {repositories
            .filter((r) => r.root_path !== activeRepoPath)
            .map((r) => (
              <option key={r.root_path} value={r.root_path}>
                {r.name} · {r.files} files
              </option>
            ))}
        </select>
      </label>
      <div className="summaryControls">
        <label>
          <input
            type="checkbox"
            checked={summarizeOnScan}
            onChange={(e) => onSummarizeOnScanChange(e.target.checked)}
          />
          Generate summaries on scan
        </label>
        <button
          id="generate-summaries-button"
          onClick={onGenerateSummaries}
          disabled={loadingSummaries || !activeRepoPath}
        >
          {loadingSummaries ? <Spinner /> : null}
          Generate Summaries
        </button>
        <p className="summaryHint">
          When enabled, up to 4,000 characters from each of up to 120 files are sent to the
          configured LLM provider.
        </p>
      </div>
    </section>
  );
}
