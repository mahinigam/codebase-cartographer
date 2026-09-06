export type Overview = {
  overview: {
    repos?: number;
    files?: number;
    symbols?: number;
    avg_score?: number;
  };
  load_bearing: LoadBearingFile[];
};

export type RepositoryInfo = {
  name: string;
  root_path: string;
  files: number;
  indexed_at?: string;
};

export type LoadBearingFile = {
  path: string;
  language: string;
  loc: number;
  complexity: number;
  churn_count: number;
  load_bearing_score: number;
};

export type GraphData = {
  nodes: Array<{ id: string; label: string; score: number; labels: string[] }>;
  edges: Array<{ source: string; target: string; type: string }>;
  total_files?: number;
  total_edges?: number;
  truncated?: boolean;
  node_limit?: number;
  edge_limit?: number;
};

export type SemanticMatch = {
  path: string;
  summary: string;
  score: number;
};

export type AskResponse = {
  answer: string;
  evidence: Array<Record<string, unknown>>;
  semantic_matches: SemanticMatch[];
};

export type FileDetail = {
  path: string;
  language: string;
  loc: number;
  complexity: number;
  churn_count: number;
  last_modified: string | null;
  load_bearing_score: number;
  symbols: Array<{
    name: string;
    kind: string;
    signature: string | null;
    start_line: number;
    end_line: number;
  }>;
  imports: string[];
  dependents: string[];
  external_deps: string[];
  summary: string | null;
};

export async function scanRepo(path: string, summarize = false) {
  return request("/api/scan", {
    method: "POST",
    body: JSON.stringify({ path, summarize })
  });
}

export async function getRepositories(): Promise<{ repositories: RepositoryInfo[] }> {
  return request("/api/repositories");
}

export async function getOverview(repoPath?: string): Promise<Overview> {
  return request(withRepoPath("/api/overview", repoPath));
}

export async function getGraph(repoPath?: string, limit = 80): Promise<GraphData> {
  return request(withQuery("/api/graph", { repo_path: repoPath, limit }));
}

export async function askQuestion(question: string, repoPath?: string): Promise<AskResponse> {
  return request("/api/query", {
    method: "POST",
    body: JSON.stringify({ question, repo_path: repoPath })
  });
}

export async function analyzeImpact(path: string, depth = 3, repoPath?: string) {
  return request("/api/impact", {
    method: "POST",
    body: JSON.stringify({ path, depth, repo_path: repoPath })
  });
}

export async function getFileDetail(
  path: string,
  repoPath?: string
): Promise<FileDetail> {
  const params = new URLSearchParams({ path });
  if (repoPath) params.set("repo_path", repoPath);
  return request(`/api/file-detail?${params.toString()}`);
}

export async function generateSummaries(repoPath: string, maxFiles?: number) {
  return request("/api/summaries", {
    method: "POST",
    body: JSON.stringify({ repo_path: repoPath, max_files: maxFiles })
  });
}

export function withRepoPath(path: string, repoPath?: string) {
  return withQuery(path, { repo_path: repoPath });
}

export function withQuery(
  path: string,
  params: Record<string, string | number | undefined>
) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "") continue;
    search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

async function request(path: string, init?: RequestInit) {
  const base = process.env.NEXT_PUBLIC_API_BASE ?? "";
  const response = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json();
}
