import { useEffect, useState } from "react";
import { FileCode, X, AlertTriangle, ArrowRight, ArrowLeft, Code2 } from "lucide-react";
import { getFileDetail, FileDetail } from "../lib/api";
import { MarkdownView } from "./MarkdownView";
import { Spinner } from "./Spinner";

type Props = {
  filePath: string | null;
  repoPath: string;
  onClose: () => void;
  onTraceImpact: (path: string) => void;
};

export function NodeDetailDrawer({
  filePath,
  repoPath,
  onClose,
  onTraceImpact,
}: Props) {
  const [detail, setDetail] = useState<FileDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!filePath) {
      setDetail(null);
      return;
    }
    setLoading(true);
    setError("");
    getFileDetail(filePath, repoPath)
      .then(setDetail)
      .catch((e) => setError(e.message ?? "Failed to load file details"))
      .finally(() => setLoading(false));
  }, [filePath, repoPath]);

  if (!filePath) return null;

  return (
    <div className="drawerBackdrop" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawerHeader">
          <h2>
            <FileCode size={18} /> File Detail
          </h2>
          <button
            className="drawerClose"
            onClick={onClose}
            aria-label="Close drawer"
          >
            <X size={18} />
          </button>
        </div>

        <div className="drawerBody">
          {loading && (
            <div className="drawerLoading">
              <Spinner size={28} />
            </div>
          )}

          {!loading && error && <p className="drawerError">{error}</p>}

          {!loading && detail && (
            <>
              <div className="drawerMeta">
                <h3>{detail.path}</h3>
                <div className="drawerTags">
                  <span className="tag">{detail.language}</span>
                  <span className="tag">{detail.loc} LOC</span>
                  <span className="tag">
                    Complexity: {detail.complexity}
                  </span>
                  <span className="tag tagRisk">
                    Risk: {detail.load_bearing_score}
                  </span>
                  {detail.churn_count > 0 && (
                    <span className="tag">
                      Churn: {detail.churn_count}
                    </span>
                  )}
                </div>
              </div>

              {detail.symbols.length > 0 && (
                <div className="drawerSection">
                  <h4>
                    <Code2 size={14} /> Symbols ({detail.symbols.length})
                  </h4>
                  <ul className="symbolList">
                    {detail.symbols.map((s) => (
                      <li key={`${s.name}-${s.start_line}`}>
                        <code>{s.signature ?? s.name}</code>
                        <span className="symbolKind">{s.kind}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {detail.imports.length > 0 && (
                <div className="drawerSection">
                  <h4>
                    <ArrowRight size={14} /> Imports ({detail.imports.length})
                  </h4>
                  <ul>
                    {detail.imports.map((p, index) => (
                      <li key={`${p}-${index}`}>{p}</li>
                    ))}
                  </ul>
                </div>
              )}

              {detail.dependents.length > 0 && (
                <div className="drawerSection">
                  <h4>
                    <ArrowLeft size={14} /> Depended On By (
                    {detail.dependents.length})
                  </h4>
                  <ul>
                    {detail.dependents.map((p, index) => (
                      <li key={`${p}-${index}`}>{p}</li>
                    ))}
                  </ul>
                </div>
              )}

              {detail.external_deps.length > 0 && (
                <div className="drawerSection">
                  <h4>External Dependencies</h4>
                  <ul>
                    {detail.external_deps.map((d, index) => (
                      <li key={`${d}-${index}`}>{d}</li>
                    ))}
                  </ul>
                </div>
              )}

              {detail.summary && (
                <div className="drawerSection">
                  <h4>AI Summary</h4>
                  <MarkdownView content={detail.summary} />
                </div>
              )}

              <button
                className="drawerAction"
                onClick={() => onTraceImpact(detail.path)}
              >
                <AlertTriangle size={16} /> Trace Impact
              </button>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
