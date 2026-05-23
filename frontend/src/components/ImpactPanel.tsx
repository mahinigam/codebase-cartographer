import { MarkdownView } from "./MarkdownView";
import { Spinner } from "./Spinner";

type Props = {
  selectedFile: string;
  onSelectedFileChange: (path: string) => void;
  onTrace: () => void;
  impact: string;
  loading: boolean;
};

export function ImpactPanel({
  selectedFile,
  onSelectedFileChange,
  onTrace,
  impact,
  loading,
}: Props) {
  return (
    <div className="panel" id="impact-panel">
      <h2>Impact Analysis</h2>
      <input
        id="impact-file-input"
        value={selectedFile}
        onChange={(e) => onSelectedFileChange(e.target.value)}
        placeholder="Enter a file path…"
      />
      <button id="trace-button" onClick={onTrace} disabled={loading || !selectedFile}>
        {loading ? <Spinner /> : null}
        {loading ? "Tracing…" : "Trace Ripple Effect"}
      </button>
      {impact && <MarkdownView content={impact} />}
    </div>
  );
}
