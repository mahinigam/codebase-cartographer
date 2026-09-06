"use client";

import { useCallback, useEffect, useState } from "react";
import {
  analyzeImpact,
  askQuestion,
  generateSummaries,
  getGraph,
  getOverview,
  getRepositories,
  GraphData,
  LoadBearingFile,
  RepositoryInfo,
  scanRepo,
  SemanticMatch,
} from "../lib/api";
import { HeroSection } from "../components/HeroSection";
import { StatusBand } from "../components/StatusBand";
import { RepoBand } from "../components/RepoBand";
import { MetricsRow } from "../components/MetricsRow";
import { GraphPanel } from "../components/GraphPanel";
import { NodeDetailDrawer } from "../components/NodeDetailDrawer";
import { LoadBearingFiles } from "../components/LoadBearingFiles";
import { AskPanel } from "../components/AskPanel";
import { ImpactPanel } from "../components/ImpactPanel";
import { ToastContainer, ToastItem, createToast } from "../components/Toast";

type Props = {
  defaultRepoPath: string;
};

export default function CartographerApp({ defaultRepoPath }: Props) {
  const [repoPath, setRepoPath] = useState(defaultRepoPath);
  const [status, setStatus] = useState("Ready to map a repository.");
  const [overview, setOverview] = useState({ files: 0, symbols: 0, avg_score: 0 });
  const [riskyFiles, setRiskyFiles] = useState<LoadBearingFile[]>([]);
  const [repositories, setRepositories] = useState<RepositoryInfo[]>([]);
  const [activeRepoPath, setActiveRepoPath] = useState(defaultRepoPath);
  const [graph, setGraph] = useState<GraphData>({ nodes: [], edges: [] });
  const [graphLimit, setGraphLimit] = useState(80);
  const [question, setQuestion] = useState("What are the riskiest parts of this codebase?");
  const [answer, setAnswer] = useState("");
  const [semanticMatches, setSemanticMatches] = useState<SemanticMatch[]>([]);
  const [selectedFile, setSelectedFile] = useState("");
  const [impact, setImpact] = useState("");
  const [summarizeOnScan, setSummarizeOnScan] = useState(true);
  const [summaryStatus, setSummaryStatus] = useState("");
  const [drawerFile, setDrawerFile] = useState<string | null>(null);

  const [loadingScan, setLoadingScan] = useState(false);
  const [loadingAsk, setLoadingAsk] = useState(false);
  const [loadingImpact, setLoadingImpact] = useState(false);
  const [loadingSummaries, setLoadingSummaries] = useState(false);

  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const addToast = useCallback(
    (message: string, type: ToastItem["type"] = "error") =>
      setToasts((prev) => [...prev, createToast(message, type)]),
    []
  );
  const dismissToast = useCallback(
    (id: number) => setToasts((prev) => prev.filter((t) => t.id !== id)),
    []
  );

  async function refresh(repoScope?: string) {
    try {
      const repoData = await getRepositories();
      const resolvedScope =
        repoScope || activeRepoPath || defaultRepoPath || repoData.repositories[0]?.root_path || "";
      const [overviewData, graphData] = await Promise.all([
        getOverview(resolvedScope),
        getGraph(resolvedScope, graphLimit),
      ]);
      setRepositories(repoData.repositories);
      if (resolvedScope && resolvedScope !== activeRepoPath) {
        setActiveRepoPath(resolvedScope);
      }
      if (resolvedScope && !repoPath) {
        setRepoPath(resolvedScope);
      }
      setOverview({
        files: overviewData.overview.files ?? 0,
        symbols: overviewData.overview.symbols ?? 0,
        avg_score: overviewData.overview.avg_score ?? 0,
      });
      setRiskyFiles(overviewData.load_bearing);
      setGraph(graphData);
      if (!selectedFile && overviewData.load_bearing[0]) {
        setSelectedFile(overviewData.load_bearing[0].path);
      }
    } catch {
      // The backend may not be running on initial page load.
    }
  }

  async function handleScan() {
    setLoadingScan(true);
    setStatus("Scanning source, mining Git history, and writing Neo4j graph...");
    try {
      const result = await scanRepo(repoPath, summarizeOnScan);
      setActiveRepoPath(result.root_path);
      setStatus(
        `Indexed ${result.files} files, ${result.symbols} symbols, ${result.imports} dependency edges.`
      );
      if (result.summaries) {
        setSummaryStatus(
          `Summaries: ${result.summaries.created}/${result.summaries.requested} generated.`
        );
      } else {
        setSummaryStatus("");
      }
      await refresh(result.root_path);
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
    setAnswer("");
    setImpact("");
    setSelectedFile("");
    setDrawerFile(null);
    setStatus(`Viewing ${path}`);
    await refresh(path);
  }

  async function handleAsk() {
    setLoadingAsk(true);
    setAnswer("");
    setSemanticMatches([]);
    try {
      const result = await askQuestion(question, activeRepoPath);
      setAnswer(result.answer);
      setSemanticMatches(result.semantic_matches ?? []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Query failed";
      addToast(msg);
    } finally {
      setLoadingAsk(false);
    }
  }

  async function handleImpact(path = selectedFile) {
    if (!path) return;
    setSelectedFile(path);
    setLoadingImpact(true);
    setImpact("");
    try {
      const result = await analyzeImpact(path, 3, activeRepoPath);
      setImpact(result.explanation);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Impact analysis failed";
      addToast(msg);
    } finally {
      setLoadingImpact(false);
    }
  }

  async function handleSummaries() {
    if (!activeRepoPath) return;
    setLoadingSummaries(true);
    setSummaryStatus("Generating summaries and embeddings...");
    try {
      const result = await generateSummaries(activeRepoPath);
      setSummaryStatus(
        `Summaries: ${result.status.created}/${result.status.requested} generated.`
      );
      addToast("Summaries generated.", "success");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Summary generation failed";
      setSummaryStatus("");
      addToast(msg);
    } finally {
      setLoadingSummaries(false);
    }
  }

  function handleNodeClick(filePath: string) {
    setDrawerFile(filePath);
  }

  async function handleExpandGraph() {
    const nextLimit = Math.min(graphLimit + 80, 400);
    setGraphLimit(nextLimit);
    try {
      const graphData = await getGraph(activeRepoPath, nextLimit);
      setGraph(graphData);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to expand graph";
      addToast(msg);
    }
  }

  function handleDrawerImpact(path: string) {
    setDrawerFile(null);
    handleImpact(path);
  }

  useEffect(() => {
    refresh();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <main className="dashboardShell">
      <aside className="sidebar">
        <div className="sidebarHeader">
          <h1>Cartographer</h1>
        </div>
        
        <div className="sidebarScroll">
          <HeroSection
            repoPath={repoPath}
            onRepoPathChange={setRepoPath}
            onScan={handleScan}
            loading={loadingScan}
          />
          <RepoBand
            activeRepoPath={activeRepoPath}
            repositories={repositories}
            summarizeOnScan={summarizeOnScan}
            onRepoChange={handleRepoChange}
            onSummarizeOnScanChange={setSummarizeOnScan}
            onGenerateSummaries={handleSummaries}
            loadingSummaries={loadingSummaries}
          />
        </div>
        
        <div className="sidebarFooter">
          <StatusBand status={status} summaryStatus={summaryStatus} />
        </div>
      </aside>

      <div className="mainContent">
        <header className="topbar">
          <MetricsRow overview={overview} riskyFileCount={riskyFiles.length} />
        </header>

        <div className="contentScroll">
          <section className="workbench">
            <GraphPanel
              graph={graph}
              onNodeClick={handleNodeClick}
              onExpand={handleExpandGraph}
            />
            <LoadBearingFiles files={riskyFiles} onFileClick={handleNodeClick} />
          </section>

          <section className="aiGrid">
            <AskPanel
              question={question}
              onQuestionChange={setQuestion}
              onAsk={handleAsk}
              answer={answer}
              semanticMatches={semanticMatches}
              loading={loadingAsk}
            />
            <ImpactPanel
              selectedFile={selectedFile}
              onSelectedFileChange={setSelectedFile}
              onTrace={() => handleImpact()}
              impact={impact}
              loading={loadingImpact}
            />
          </section>
        </div>
      </div>

      <NodeDetailDrawer
        filePath={drawerFile}
        repoPath={activeRepoPath}
        onClose={() => setDrawerFile(null)}
        onTraceImpact={handleDrawerImpact}
      />

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </main>
  );
}
