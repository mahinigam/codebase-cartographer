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
};

export async function scanRepo(path: string) {
  return request("/api/scan", {
    method: "POST",
    body: JSON.stringify({ path })
  });
}

export async function getRepositories(): Promise<{ repositories: RepositoryInfo[] }> {
  return request("/api/repositories");
}

export async function getOverview(repoPath?: string): Promise<Overview> {
  return request(withRepoPath("/api/overview", repoPath));
}

export async function getGraph(repoPath?: string): Promise<GraphData> {
  return request(withRepoPath("/api/graph", repoPath));
}

export async function askQuestion(question: string, repoPath?: string) {
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

function withRepoPath(path: string, repoPath?: string) {
  if (!repoPath) return path;
  const params = new URLSearchParams({ repo_path: repoPath });
  return `${path}?${params.toString()}`;
}

async function request(path: string, init?: RequestInit) {
  const response = await fetch(path, {
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
