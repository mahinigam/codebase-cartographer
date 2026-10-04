"use client";

import { useCallback, useEffect, useState } from "react";
import {
  analyzeImpact,
  getGraph,
  getOverview,
  getRepositories,
  getFiles,
  getFileDetail,
  askQuestion,
  GraphData,
  RepositoryInfo,
  scanRepo,
  FileDetail,
} from "../lib/api";
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels";
import { ToastContainer, ToastItem, createToast } from "../components/Toast";
import { EmptyWorkspace } from "../components/EmptyWorkspace";
import { WorkspaceTopbar } from "../components/WorkspaceTopbar";
import { RepositoryExplorer } from "../components/RepositoryExplorer";
import { GraphPanel } from "../components/GraphPanel";
// GraphToolbar is now rendered inside GraphPanel
import { Inspector } from "../components/Inspector";
import { CommandPalette } from "../components/CommandPalette";
import { AskPanel } from "../components/AskPanel";

type Props = {
  defaultRepoPath: string;
};

export default function CartographerApp({ defaultRepoPath }: Props) {
  // Workspace state
  const [repoPath, setRepoPath] = useState(() => {
    try {
      return localStorage.getItem("cartographer_last_repo") || defaultRepoPath;
    } catch {
      return defaultRepoPath;
    }
  });
  const [activeRepoPath, setActiveRepoPath] = useState(() => {
    try {
      return localStorage.getItem("cartographer_last_repo") || defaultRepoPath;
    } catch {
      return defaultRepoPath;
    }
  });

  useEffect(() => {
    try {
      if (activeRepoPath) {
        localStorage.setItem("cartographer_last_repo", activeRepoPath);
      } else {
        localStorage.removeItem("cartographer_last_repo");
      }
    } catch {
      // localStorage unavailable (SSR or test environment)
    }
  }, [activeRepoPath]);

  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileDetail, setFileDetail] = useState<FileDetail | null>(null);
  const [pathPrefix, setPathPrefix] = useState<string | null>(null);
  const [graphMode, setGraphMode] = useState<"architecture" | "risk" | "recent">("architecture");
  const [impactMode, setImpactMode] = useState(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [scanRepoName, setScanRepoName] = useState<string | null>(null);
  
  // Data state
  const [repositories, setRepositories] = useState<RepositoryInfo[]>([]);
  const [overview, setOverview] = useState({ files: 0, symbols: 0, avg_score: 0 });
  const [files, setFiles] = useState<Array<any>>([]);
  const [graph, setGraph] = useState<GraphData>({ nodes: [], edges: [] });
  const [graphLimit, setGraphLimit] = useState(80);

  // Status state
  const [loadingScan, setLoadingScan] = useState(false);
  const [status, setStatus] = useState("Ready to map a repository.");
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [semanticMatches, setSemanticMatches] = useState<any[]>([]);
  const [loadingAsk, setLoadingAsk] = useState(false);

  const addToast = useCallback(
    (message: string, type: ToastItem["type"] = "error") =>
      setToasts((prev) => [...prev, createToast(message, type)]),
    []
  );
  const dismissToast = useCallback(
    (id: number) => setToasts((prev) => prev.filter((t) => t.id !== id)),
    []
  );

  async function handleAsk(q: string) {
    setQuestion(q);
    setAnswer("");
    setSemanticMatches([]);
    setLoadingAsk(true);
    try {
      const result = await askQuestion(q, activeRepoPath);
      setAnswer(result.answer);
      setSemanticMatches(result.semantic_matches || []);
    } catch (err: unknown) {
      addToast(err instanceof Error ? err.message : "Query failed");
    } finally {
      setLoadingAsk(false);
    }
  }

  async function refresh(repoScope?: string) {
    try {
      const repoData = await getRepositories();
      setRepositories(repoData.repositories);
      
      const resolvedScope = repoScope || activeRepoPath || defaultRepoPath;
      if (!resolvedScope) return;

      if (resolvedScope !== activeRepoPath) setActiveRepoPath(resolvedScope);
      if (!repoPath) setRepoPath(resolvedScope);

      const [overviewData, graphData, filesData] = await Promise.all([
        getOverview(resolvedScope),
        getGraph(resolvedScope, graphLimit), // We will add pathPrefix later
        getFiles(resolvedScope)
      ]);

      setOverview({
        files: overviewData.overview.files ?? 0,
        symbols: overviewData.overview.symbols ?? 0,
        avg_score: overviewData.overview.avg_score ?? 0,
      });
      setGraph(graphData);
      setFiles(filesData.files);
    } catch {
      // Backend may not be ready
    }
  }

  async function handleScan(path: string, summarize: boolean) {
    setLoadingScan(true);
    setStatus("Scanning source, mining Git history, and writing Neo4j graph...");
    try {
      const result = await scanRepo(path, summarize);
      setStatus(`Indexed ${result.files} files, ${result.symbols} symbols, ${result.imports} edges.`);
      // Store the repo name from the scan result so the topbar can use it immediately
      setScanRepoName(result.repository || path.split("/").filter(Boolean).pop() || "Repository");
      // Fetch all data BEFORE transitioning to workspace view
      await refresh(result.root_path);
      // NOW set active path — this triggers the transition from EmptyWorkspace to workspace
      setActiveRepoPath(result.root_path);
      setRepoPath(result.root_path);
      addToast("Repository scanned successfully.", "success");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Scan failed";
      setStatus("Scan failed.");
      addToast(msg);
    } finally {
      setLoadingScan(false);
    }
  }

  async function handleRepoChange(path: string) {
    setActiveRepoPath(path);
    setRepoPath(path);
    setSelectedFile(null);
    setFileDetail(null);
    setImpactMode(false);
    setStatus(`Viewing ${path}`);
    await refresh(path);
  }

  // The universal selection action
  async function selectFile(path: string, source: "graph" | "tree" | "search" | "risk" | "ai" | "inspector") {
    setSelectedFile(path);
    try {
      const detail = await getFileDetail(path, activeRepoPath);
      setFileDetail(detail);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load file details";
      addToast(msg);
    }
  }

  const [impactData, setImpactData] = useState<any>(null);

  async function handleTraceImpact(path: string) {
    setImpactMode(true);
    setImpactData(null);
    try {
      const result = await analyzeImpact(path, 3, activeRepoPath);
      setImpactData(result);
      addToast(`Impact analysis complete: ${result.direct_dependents.length} direct, ${result.transitive_dependents.length} transitive dependents.`, "success");
    } catch (err: unknown) {
      addToast(err instanceof Error ? err.message : "Impact analysis failed");
      setImpactMode(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const activeRepo = repositories.find((r) => r.root_path === activeRepoPath);
  // Show empty state when there's no active repo selected, OR when a scan is in progress
  // (the EmptyWorkspace component shows its own loading spinner during scans)
  const showEmptyState = !activeRepoPath || (repositories.length === 0 && !loadingScan);

  return (
    <div className="workspace-shell">
      {showEmptyState ? (
        <EmptyWorkspace
          defaultRepoPath={defaultRepoPath}
          onScan={handleScan}
          loading={loadingScan}
          repositories={repositories}
          onSelectRepo={handleRepoChange}
        />
      ) : (
        <>
          <WorkspaceTopbar
            repoName={activeRepo?.name || scanRepoName || "Codebase"}
            branch="main" // Can add real branch detection later
            onOpenCommandPalette={() => setCommandPaletteOpen(true)}
            onHome={() => {
              setActiveRepoPath("");
              setRepoPath("");
            }}
          />
          
          <div className="workspace-main">
            <PanelGroup orientation="horizontal" style={{ width: '100%', height: '100%' }}>
              <Panel defaultSize="20" minSize="15" maxSize="35">
                <RepositoryExplorer
                  repositories={repositories}
                  activeRepoPath={activeRepoPath}
                  files={files}
                  selectedFile={selectedFile}
                  onSelectFile={(path) => selectFile(path, "tree")}
                  onRepoChange={handleRepoChange}
                  onRescan={() => handleScan(activeRepoPath, false)}
                  onViewChange={setGraphMode}
                />
              </Panel>

              <PanelResizeHandle className="resize-handle" />

              <Panel minSize="30">
                <div className="graph-workspace">
                  <GraphPanel
                    graph={graph}
                    selectedFile={selectedFile}
                    impactMode={impactMode}
                    impactData={impactData}
                    onNodeClick={(path) => selectFile(path, "graph")}
                    overview={overview}
                    totalFiles={graph.total_files || files.length}
                    totalEdges={graph.total_edges || graph.edges.length}
                    avgRisk={overview.avg_score}
                    onFilterToggle={() => {}}
                  />
                </div>
              </Panel>

              {selectedFile && fileDetail && (
                <PanelResizeHandle className="resize-handle" />
              )}
              {selectedFile && fileDetail && (
                <Panel defaultSize="25" minSize="20" maxSize="45">
                  <Inspector
                    file={fileDetail}
                    onClose={() => setSelectedFile(null)}
                    onSelectFile={(path) => selectFile(path, "inspector")}
                    onTraceImpact={handleTraceImpact}
                  />
                </Panel>
              )}
            </PanelGroup>
            
            <div className="ai-investigation-layer">
              <AskPanel
                question={question}
                answer={answer}
                semanticMatches={semanticMatches}
                loading={loadingAsk}
                onSelectFile={selectFile}
                onClear={() => { setQuestion(""); setAnswer(""); setSemanticMatches([]); }}
              />
            </div>
          </div>
        </>
      )}

      <CommandPalette
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        activeRepoPath={activeRepoPath}
        onSelectFile={selectFile}
        onAsk={handleAsk}
      />

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
