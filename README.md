# Codebase Cartographer

A structural forensics engine for software repositories. It turns a codebase into a navigable Neo4j knowledge graph of files, symbols, dependencies, Git history, risk signals, and AI-generated architectural summaries.

Instead of treating code as plain text, it combines deterministic static analysis with Gemini-powered reasoning and a local Ollama fallback.

## Why It Matters

Large codebases are hard to change safely because their real architecture is usually hidden in imports, call paths, historical patches, and undocumented conventions. Codebase Cartographer helps new joiners and senior architects answer:

- Where does this behavior live?
- Which files are load-bearing?
- What might break if I change this file?
- What does the module/package/repo actually do?
- Which parts of the codebase are isolated enough to refactor?

## Features

- **Knowledge graph** — Files, symbols, imports, and external dependencies stored in Neo4j with full relationship modeling
- **Incremental rescans** — Reuses unchanged file fingerprints from Neo4j to avoid reparsing stable files
- **Risk scoring** — Deterministic load-bearing score combining fan-in, complexity, churn, and fan-out
- **AI Q&A** — Ask architecture questions and get answers grounded in graph + vector evidence
- **Impact analysis** — Trace direct and transitive dependents of any file to assess refactor risk
- **File detail drawer** — Click any node in the graph to inspect its symbols, dependencies, and AI summary
- **Semantic search** — Gemini embeddings stored in a Neo4j vector index for meaning-based retrieval
- **Dagre graph layout** — Force-directed visualization of the dependency graph with risk-highlighted nodes
- **Markdown rendering** — AI answers render with headings, tables, code blocks, and lists
- **Git history mining** — Churn counts and recency from up to 500 commits

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js + React 19 + TypeScript |
| Backend | FastAPI (Python) |
| Graph database | Neo4j Community |
| Static analysis | Python AST, Tree-sitter (JS/TS) |
| AI (primary) | Gemini free API |
| AI (fallback) | Ollama `qwen2.5-coder:7b` |
| Embeddings | Gemini `text-embedding-004` / Ollama `nomic-embed-text` |
| Vector search | Neo4j vector index |
| Graph layout | dagre |
| Tests | pytest + Vitest |
| License | MIT |

## Quick Start

1. Copy env config:

```bash
cp .env.example .env
```

2. Add your Gemini API key to `.env`.

3. Start Neo4j:

```bash
docker compose up -d neo4j
```

4. Start the backend:

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

5. Start the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Docker Compose

Run everything in one command:

```bash
docker compose up --build
```

Notes:

- The backend container mounts the repository at `/workspace` for scanning.
- Ollama must be running on the host; Docker uses `http://host.docker.internal:11434`.

## Usage

1. Paste a local repository path and click **Analyze**.
2. The scanner extracts files, symbols, imports, and Git history into a Neo4j graph.
3. Click **Generate Summaries** to create AI-powered file summaries and embeddings.
4. Explore the architecture graph — click any node to open the **file detail drawer**.
5. Use **Ask Cartographer** to query the graph with natural language.
6. Select a file and run **Impact Analysis** to trace dependency ripple effects.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check (includes Neo4j status) |
| `POST` | `/api/scan` | Scan a repository and build the graph |
| `GET` | `/api/repositories` | List indexed repositories |
| `GET` | `/api/overview` | Repository stats and top load-bearing files |
| `GET` | `/api/graph` | Graph slice for visualization |
| `GET` | `/api/file-detail` | Full file context (symbols, deps, summary) |
| `POST` | `/api/query` | Ask an architecture question |
| `POST` | `/api/impact` | Trace change impact for a file |
| `POST` | `/api/summaries` | Generate AI summaries and embeddings |

## Security

- API keys are read from environment variables only.
- Repository paths are constrained by `ALLOWED_REPO_ROOTS` when configured.
- Set `API_TOKEN` to require `Authorization: Bearer ...` or `X-API-Key` on API requests.
- `SCAN_MAX_FILES` and `SCAN_RATE_LIMIT_PER_MINUTE` cap expensive scan/summarization requests.
- `.env` files are ignored by Git.
- The app indexes local source files and does not upload code unless an external LLM provider is enabled.
- When AI summaries are enabled, up to about 4,000 characters of each file's source (up to 120 files per scan by default) are sent to Google's Gemini API, or to a local Ollama model if Gemini is unavailable. Turn summaries off, or use only the Ollama fallback, for proprietary code you do not want leaving the machine.
- Summary generation refuses paths that resolve outside the scanned repository root.

## Configuration

### Environment Variables

See `.env.example` for the full list. Key settings:

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | — | Gemini API key (required for AI features) |
| `LLM_PROVIDER` | `gemini` | Primary LLM provider |
| `FALLBACK_LLM_PROVIDER` | `ollama` | Fallback when primary is unavailable |
| `NEO4J_PASSWORD` | — | Neo4j database password |
| `ALLOWED_REPO_ROOTS` | — | Comma-separated allowed scan paths |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed CORS origins |
| `API_TOKEN` | — | Optional API token for hosted/shared deployments |
| `SCAN_MAX_FILES` | `10000` | Maximum supported source files per scan; set `0` to disable |
| `SCAN_RATE_LIMIT_PER_MINUTE` | `6` | Per-client scan/summaries request limit; set `0` to disable |

### Frontend Overrides

- `API_BASE_URL` — Backend target used by the Next.js `/api` rewrite (default: `http://localhost:8000`).
- `NEXT_PUBLIC_API_BASE` — Optional browser-side API base override. Leave empty to use the Next.js rewrite.
- `NEXT_PUBLIC_DEFAULT_REPO` — Prefill the repository path input.
