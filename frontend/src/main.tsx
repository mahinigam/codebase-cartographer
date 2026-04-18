import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import ReactFlow, { Background, Controls, Edge, Node } from "reactflow";
import { Activity, GitBranch, Layers3, Radar, Search, ShieldAlert } from "lucide-react";
import "reactflow/dist/style.css";
import "./styles/app.css";
import {
  analyzeImpact,
  askQuestion,
  getGraph,
  getOverview,
  getRepositories,
  GraphData,
  LoadBearingFile,
  RepositoryInfo,
  scanRepo
} from "./lib/api";

const defaultRepoPath = "/Users/mahinigam/Codes/Codebase Catographer/codebase-cartographer";

function App() {
  const [repoPath, setRepoPath] = useState(defaultRepoPath);
  const [status, setStatus] = useState("Ready to map a repository.");
  const [overview, setOverview] = useState({ repos: 0, files: 0, symbols: 0, avg_score: 0 });
  const [riskyFiles, setRiskyFiles] = useState<LoadBearingFile[]>([]);
  const [repositories, setRepositories] = useState<RepositoryInfo[]>([]);
  const [activeRepoPath, setActiveRepoPath] = useState(defaultRepoPath);
  const [graph, setGraph] = useState<GraphData>({ nodes: [], edges: [] });
  const [question, setQuestion] = useState("What are the riskiest parts of this codebase?");
  const [answer, setAnswer] = useState("");
  const [selectedFile, setSelectedFile] = useState("");
  const [impact, setImpact] = useState("");

  async function refresh(repoScope = activeRepoPath) {
    const [repoData, overviewData, graphData] = await Promise.all([
      getRepositories(),
      getOverview(repoScope),
      getGraph(repoScope)
    ]);
    setRepositories(repoData.repositories);
    setOverview({
      repos: overviewData.overview.repos ?? 0,
      files: overviewData.overview.files ?? 0,
      symbols: overviewData.overview.symbols ?? 0,
      avg_score: overviewData.overview.avg_score ?? 0
    });
    setRiskyFiles(overviewData.load_bearing);
    setGraph(graphData);
    if (!selectedFile && overviewData.load_bearing[0]) {
      setSelectedFile(overviewData.load_bearing[0].path);
    }
  }

  async function handleScan() {
    setStatus("Scanning source, mining Git history, and writing Neo4j graph...");
    const result = await scanRepo(repoPath);
    setActiveRepoPath(result.root_path);
    setStatus(`Indexed ${result.files} files, ${result.symbols} symbols, ${result.imports} dependency edges.`);
    await refresh(result.root_path);
  }

  async function handleRepoChange(path: string) {
    setActiveRepoPath(path);
    setRepoPath(path);
    setAnswer("");
    setImpact("");
    setSelectedFile("");
    setStatus(`Viewing ${path}`);
    await refresh(path);
  }

  async function handleAsk() {
    setAnswer("Thinking over the structural graph...");
    const result = await askQuestion(question, activeRepoPath);
    setAnswer(result.answer);
  }

  async function handleImpact(path = selectedFile) {
    if (!path) return;
    setSelectedFile(path);
    setImpact("Tracing dependency ripple paths...");
    const result = await analyzeImpact(path, 3, activeRepoPath);
    setImpact(result.explanation);
  }

  useEffect(() => {
    refresh().catch(() => undefined);
  }, []);

  const flow = useMemo(() => toFlow(graph), [graph]);

  return (
    <main>
      <section className="hero">
        <div>
          <p className="eyebrow">Structural Forensics</p>
          <h1>Codebase Cartographer</h1>
          <p className="lede">
            Map legacy code into a Neo4j knowledge graph, detect load-bearing files, and ask
            architecture questions with evidence.
          </p>
        </div>
        <div className="scanBar">
          <input value={repoPath} onChange={(event) => setRepoPath(event.target.value)} />
          <button onClick={handleScan}>
            <Radar size={18} /> Analyze
          </button>
        </div>
      </section>

      <section className="statusBand">
        <span>{status}</span>
      </section>

      <section className="repoBand">
        <label>
          Active repo
          <select
            value={activeRepoPath}
            onChange={(event) => handleRepoChange(event.target.value)}
          >
            <option value={activeRepoPath}>{activeRepoPath}</option>
            {repositories
              .filter((repo) => repo.root_path !== activeRepoPath)
              .map((repo) => (
                <option key={repo.root_path} value={repo.root_path}>
                  {repo.name} · {repo.files} files
                </option>
              ))}
          </select>
        </label>
      </section>

      <section className="metrics">
        <Metric icon={<Layers3 />} label="Files" value={overview.files ?? 0} />
        <Metric icon={<GitBranch />} label="Symbols" value={overview.symbols ?? 0} />
        <Metric icon={<Activity />} label="Avg Risk" value={overview.avg_score ?? 0} />
        <Metric icon={<ShieldAlert />} label="Load-Bearing" value={riskyFiles.length} />
      </section>

      <section className="workbench">
        <div className="graphPanel">
          <div className="panelHeader">
            <h2>Architecture Graph</h2>
            <span>
              {flow.nodes.length} nodes · {flow.edges.length} edges
            </span>
          </div>
          <ReactFlow nodes={flow.nodes} edges={flow.edges} fitView>
            <Background />
            <Controls />
          </ReactFlow>
        </div>

        <aside className="sidePanel">
          <h2>Load-Bearing Files</h2>
          <div className="fileList">
            {riskyFiles.map((file) => (
              <button key={file.path} onClick={() => handleImpact(file.path)}>
                <span>{file.path}</span>
                <strong>{file.load_bearing_score}</strong>
              </button>
            ))}
          </div>
        </aside>
      </section>

      <section className="aiGrid">
        <div className="panel">
          <h2>Ask Cartographer</h2>
          <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
          <button onClick={handleAsk}>
            <Search size={18} /> Ask
          </button>
          <pre>{answer}</pre>
        </div>
        <div className="panel">
          <h2>Impact Analysis</h2>
          <input value={selectedFile} onChange={(event) => setSelectedFile(event.target.value)} />
          <button onClick={() => handleImpact()}>Trace Ripple Effect</button>
          <pre>{impact}</pre>
        </div>
      </section>
    </main>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <div className="metric">
      {icon}
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function toFlow(graph: GraphData): { nodes: Node[]; edges: Edge[] } {
  const columns = Math.ceil(Math.sqrt(Math.max(graph.nodes.length, 1)));
  const nodes = graph.nodes.map((node, index) => ({
    id: node.id,
    data: { label: node.label },
    position: { x: (index % columns) * 220, y: Math.floor(index / columns) * 110 },
    style: {
      border: "1px solid #26364f",
      background: node.score > 70 ? "#fff1f2" : "#f8fafc",
      color: "#172033",
      borderRadius: 8,
      width: 190,
      fontSize: 12
    }
  }));
  const edges = graph.edges.map((edge, index) => ({
    id: `${edge.source}-${edge.target}-${index}`,
    source: edge.source,
    target: edge.target,
    label: edge.type,
    animated: false
  }));
  return { nodes, edges };
}

createRoot(document.getElementById("root")!).render(<App />);
