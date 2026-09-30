# Codebase Cartographer

**Structural forensics engine and interactive mapping tool for software repositories.**

Codebase Cartographer transforms any codebase into a navigable Neo4j knowledge graph of files, symbols, dependencies, Git history, risk signals, and AI-generated architectural summaries. It combines deterministic static analysis with a two-tier AI architecture — fast structured classification (TypeSafe Jev) and deep generative reasoning (Gemini / Ollama) — to expose the true architecture hidden within your code.

---

## Why It Matters

Large codebases are notoriously difficult to change safely. Their real architecture is buried under complex import trees, historical patches, and undocumented conventions. Cartographer provides engineers and architects with a professional instrument to answer critical questions:

- **Where does this behavior live?** — Graph-powered file and symbol search across the full codebase topology.
- **Which files are structurally load-bearing?** — Deterministic risk scoring, enhanced by semantic AI analysis.
- **What might break if I refactor this file?** — Transitive dependency tracing with blast-radius estimation.
- **What does this undocumented module actually do?** — AI-generated per-file architectural summaries.
- **Is this cluster extractable?** — Module cohesion and coupling analysis with extraction-readiness assessment.
- **Is any of my code dead?** — Probabilistic dead-code detection using zero-fan-in candidates and AI evaluation.

---

## Core Features

### Interactive Workspace

| Feature | Description |
|---|---|
| **Resizable Panel Layout** | Three-panel workspace (Repository Explorer, Graph Canvas, Inspector) powered by `react-resizable-panels`. |
| **Infinite Graph Canvas** | Hardware-accelerated ReactFlow canvas with Dagre DAG layout. Pan and zoom with trackpad gestures. Includes a glassmorphic MiniMap. |
| **Command Palette** | `Cmd+K` fuzzy search across files, symbols, and AI queries. Debounced real-time results with keyboard navigation. |
| **Graph Filters** | Toggle test files, high-risk-only view (> 75 score), and isolated nodes directly over the graph. |
| **Repository Explorer** | Collapsible file tree with Architecture and Risk Hotspot views. Inline risk indicators and repository metadata. |
| **Inspector Panel** | Deep file detail: risk profile with bar-chart breakdown (fan-in, complexity, churn, fan-out), AI summary, symbols, imports, dependents, external dependencies, Jev metadata (role, framework, risk category, dead code), and refactor safety gate. |
| **Ask Cartographer** | Natural-language architecture queries answered with graph topology + vector evidence, rendered as Markdown with clickable evidence links. |
| **Impact Analysis** | Visual dependency trace showing direct and transitive dependents, with Jev-powered refactor safety assessment (blast radius, recommended strategy). |
| **Toast Notifications** | Non-blocking success/error notifications for scan results and API errors. |
| **Empty Workspace Landing** | Clean onboarding state for first-time users with a repository path input form. |

### Analysis Engine

| Capability | Implementation |
|---|---|
| **Python Parsing** | `ast.parse` — extracts classes, functions, async functions, imports, `from` imports, and cyclomatic complexity (if/for/while/try/match branches). |
| **JavaScript/TypeScript Parsing** | Tree-sitter (primary) with regex fallback — extracts ES6 imports, CommonJS `require()`, function/arrow/class declarations, and complexity nodes. |
| **Git History Mining** | GitPython traverses up to 500 commits to extract per-file churn counts and last-modified timestamps. |
| **Import Resolution** | Full module resolution for Python (dotted paths, relative imports, `__init__` packages) and JavaScript (relative paths, extensionless resolution, `/index` convention). |
| **Incremental Rescans** | SHA-256 content fingerprints + stat fingerprints (size + mtime). Unchanged files reuse cached symbols and import edges from Neo4j. |
| **Risk Scoring** | Weighted composite: 45% fan-in (dampened for trivial utilities < 30 LOC with complexity ≤ 1), 25% complexity, 20% churn, 10% fan-out. Enhanced by Jev semantic scoring (70/30 blend). |

### Two-Tier AI Architecture

Cartographer employs a dual-tier AI strategy to balance speed, structured outputs, and deep reasoning:

#### System One — TypeSafe AI (Jev)

Integrated via the official `typesafe-sdk`, Jev acts as the fast, structured decision engine. It uses three decision primitives — **Choice** (categorical classification), **Noul** (probability estimation), and **Score** (numeric rating) — across **10 integration bonds**:

| Bond | Name | Primitives | Purpose |
|---:|---|---|---|
| 1 | File Classification | Choice | Classify each file's architectural role from 40+ categories (e.g., `core-business-logic`, `api-endpoint-handler`, `ui-component`, `test-unit`). |
| 2 | Semantic Risk Scoring | Score + Choice | Rate refactoring risk (1–10) and categorize the primary source of risk (e.g., `structural-chokepoint`, `security-critical`). |
| 3 | Test File Detection | Noul + Choice | Probabilistically detect test/spec/fixture files and categorize them (unit, integration, e2e, snapshot, etc.). |
| 4 | Query Routing | Choice + Noul | Classify user question intent (13 intents) and decide whether the query needs generative AI or can be answered from graph data alone. |
| 5 | Cluster Assessment | Score + Score + Choice | Rate directory-cluster cohesion and coupling (1–5) and assess extraction readiness. |
| 6 | Refactor Safety | Noul + Choice + Score | Evaluate whether a file is safe to refactor in a single PR, recommend a strategy (8 options), and estimate blast radius (1–10). |
| 7 | Summary Triage | Noul + Score | Decide whether a file warrants an expensive LLM summary call and assign a priority score. |
| 8 | Framework Detection | Choice + Choice | Identify the framework ecosystem (40+ options) and architectural layer (presentation, api, domain, infrastructure, etc.). |
| 9 | Re-summarization Check | Noul + Score | Evaluate whether a file's existing AI summary is stale after code changes, to avoid redundant LLM calls. |
| 10 | Dead Code Detection | Noul + Choice | Flag zero-fan-in files as likely dead code and categorize the reason (abandoned feature, stale migration, etc.). |

#### System Two — Google Gemini / Ollama

Gemini serves as the primary deep-reasoning layer for:

- **File Summaries**: Truncated source snippets (configurable, default 4,000 chars) are sent to Gemini to generate natural-language architectural summaries.
- **Embeddings**: `text-embedding-004` generates 768-dimensional vectors stored in a Neo4j vector index for semantic search.
- **Architecture Q&A**: Full retrieval-augmented generation combining graph evidence and semantic matches.
- **Impact Narratives**: Detailed Markdown explanations of change impact and risk assessment.

**Fallback Cascade**: Gemini → Ollama (`qwen2.5-coder:7b`) → deterministic structural fallback (Neo4j topology only, no API key required).

---

## Technology Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 16 (App Router) · React 19 · TypeScript 5.8 |
| **Backend** | FastAPI · Python 3.12+ · managed via `uv` |
| **Graph Database** | Neo4j 5 Community Edition (with APOC plugin) |
| **Static Analysis** | Python `ast` module · Tree-sitter via `tree-sitter-language-pack` |
| **System One AI** | TypeSafe AI Jev via `typesafe-sdk ≥ 0.7.2` |
| **System Two AI** | Google Gemini via `google-genai ≥ 2.25.0` · Ollama (fallback) |
| **Embeddings** | Gemini `text-embedding-004` · Ollama `nomic-embed-text` (fallback) |
| **Graph Visualization** | ReactFlow 11 · Dagre (`@dagrejs/dagre`) |
| **UI Framework** | `react-resizable-panels` · `lucide-react` (icons) · `react-markdown` + `remark-gfm` |
| **Testing (Backend)** | `pytest` · `pytest-asyncio` · `pytest-cov` · `ruff` · `mypy` |
| **Testing (Frontend)** | `vitest` · `@testing-library/react` · `@vitest/coverage-v8` · `jsdom` |
| **CI/CD** | GitHub Actions (Python 3.12, Node 22) |
| **Containerization** | Docker Compose (Neo4j, Backend, Frontend) |

---

## API Reference

All endpoints are prefixed with `/api` and optionally require a Bearer token or `X-API-Key` header when `API_TOKEN` is configured.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check — returns API and Neo4j connectivity status. |
| `POST` | `/api/scan` | Scan a repository. Accepts `path`, `summarize` (trigger AI summaries), `incremental` (reuse cached files). Rate-limited. |
| `GET` | `/api/overview` | Repository statistics: file count, symbol count, average risk score, top load-bearing files. |
| `GET` | `/api/repositories` | List all indexed repositories with file counts and timestamps. |
| `GET` | `/api/files` | List all files for a repository with metrics (LOC, complexity, churn, score, role, risk). |
| `GET` | `/api/graph` | Paginated graph slice: top-N nodes by risk score, their import edges, directory clusters with Jev cohesion/coupling metrics. Configurable node limit (default 80, max 400) and edge limit (default 200, max 2,000). |
| `GET` | `/api/search` | Keyword search across file paths, symbol names, imports, dependents, and external dependencies. |
| `POST` | `/api/query` | Natural-language architecture question. Combines Jev query routing, graph retrieval, semantic search, and Gemini reasoning. |
| `POST` | `/api/impact` | Impact analysis for a file: direct dependents, transitive dependents (configurable depth 1–6), Jev refactor safety gate, and Gemini narrative. |
| `GET` | `/api/file-detail` | Full file detail: all metrics, risk component breakdown, symbols, imports, dependents, external deps, AI summary. |
| `POST` | `/api/summaries` | Generate AI summaries for a repository. Jev triages and prioritizes files before spending Gemini calls. Rate-limited. |

---

## Quick Start

### Prerequisites

- **Neo4j 5** — Community Edition (Docker recommended)
- **Python 3.12+** — with [uv](https://docs.astral.sh/uv/) package manager
- **Node.js 22+** — with npm

### 1. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | For AI features | Google Gemini API key |
| `TYPESAFE_API_KEY` | For Jev features | TypeSafe API key from [console.typesafe.ai](https://console.typesafe.ai/) |
| `NEO4J_PASSWORD` | Yes | Neo4j password (default: `codebase-cartographer`) |
| `ALLOWED_REPO_ROOTS` | Production | Comma-separated list of allowed scan paths |
| `API_TOKEN` | Production | Bearer token for API authentication |

### 2. Start Neo4j

```bash
docker compose up -d neo4j
```

### 3. Start the Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### 4. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

Open your browser at **http://localhost:5173**.

---

## Docker Compose

Run the entire stack in isolation:

```bash
docker compose up --build
```

This starts three containers:

| Service | Port | Description |
|---|---|---|
| `neo4j` | `7474` (browser) / `7687` (bolt) | Graph database with APOC plugin, 512 MB–1 GB heap |
| `backend` | `8000` | FastAPI server, mounts repo at `/workspace` (read-only) |
| `frontend` | `5173` | Next.js production build |

> **Note:** The backend container mounts the repository at `/workspace` for scanning. If using Ollama, it must be running on the host; Docker connects via `http://host.docker.internal:11434`.

---

## Usage Workflow

1. **Open Cartographer** — you are greeted by the landing page. Paste an absolute local repository path and click **Analyze**.
2. **Scan** — the engine extracts files, symbols, imports, and Git history. Jev classifies each file's role, detects tests and dead code, and enhances risk scores. Everything is written to Neo4j.
3. **Explore** — the Repository Explorer (left panel) lets you browse the codebase tree. Toggle between Architecture view and Risk Hotspot view.
4. **Map** — use trackpad gestures to pan and zoom the ReactFlow canvas. Nodes are colored and sized by risk score. Click any node to open the Inspector.
5. **Inspect** — the Inspector (right panel) shows full file detail: risk breakdown bars, AI summary, symbols, imports, dependents, external dependencies, Jev metadata (architectural role, framework, risk category, dead code flag), and a "Trace Impact" button.
6. **Ask** — press `Cmd+K` to open the Command Palette, or use the Ask Panel to query the architecture with natural language. Jev routes the query; the answer is grounded in graph and vector evidence.
7. **Impact** — select a file and run "Trace Impact" to see direct and transitive dependents, blast radius estimation, and a recommended refactoring strategy.
8. **Summarize** — trigger AI summary generation for the repository. Jev triages which files deserve expensive Gemini calls and assigns priority order.

---

## Security & Privacy

- **Local First**: The application indexes local source files. No raw code is uploaded unless an external LLM provider is explicitly configured.
- **Provider Fallbacks**: System One (Jev) uses lightweight, structured queries. System Two sends up to 4,000 characters of source to Gemini. If Gemini is unavailable, it falls back to Ollama; if both fail, the engine provides a deterministic fallback using Neo4j topology alone. To ensure absolute privacy, disable Gemini and rely entirely on the local Ollama fallback.
- **Path Constraints**: `validate_repo_path()` enforces `ALLOWED_REPO_ROOTS` — repositories outside configured roots are rejected. Summary generation refuses paths that resolve outside the scanned repository root.
- **API Security**: Optional `API_TOKEN` protects all endpoints via Bearer token or `X-API-Key`. Rate limiting (`SCAN_RATE_LIMIT_PER_MINUTE`, default 6) and file caps (`SCAN_MAX_FILES`, default 10,000) prevent abuse in shared deployments.
- **CORS**: Configurable via `CORS_ORIGINS` (default: `http://localhost:5173`). Only `GET` and `POST` methods are allowed.

---

## Development & Testing

Codebase Cartographer enforces stringent quality gates across both ecosystems.

### Backend

| Tool | Purpose | Threshold |
|---|---|---|
| `pytest` + `pytest-asyncio` | Unit and integration tests | **90% coverage** |
| `ruff` | Linting (E, F, I, B, UP, S rules) | Zero errors |
| `mypy` | Static type checking | Zero errors |

### Frontend

| Tool | Purpose | Threshold |
|---|---|---|
| `vitest` + `@testing-library/react` | Component and unit tests | **85% coverage** (lines, functions, branches, statements) |
| `tsc --noEmit` | TypeScript type checking | Zero errors |

### Running All Checks

```bash
bash ./check.sh
```

This single script runs backend tests with coverage, ruff lint, mypy type checking, frontend tests with coverage, and TypeScript type checking.

### Continuous Integration

Every push to `main` and every pull request runs the full check suite via GitHub Actions (`ci.yml`) on `ubuntu-latest` with Python 3.12 and Node.js 22.

---

## Project Structure

```
codebase-cartographer/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py              # FastAPI endpoints (12 routes)
│   │   ├── core/
│   │   │   └── config.py              # Pydantic settings (env vars)
│   │   ├── indexing/
│   │   │   ├── discovery.py           # File discovery + language detection
│   │   │   ├── git_history.py         # Git churn mining (GitPython)
│   │   │   ├── js_parser.py           # JS/TS parser (Tree-sitter + regex)
│   │   │   ├── python_parser.py       # Python parser (ast module)
│   │   │   └── scanner.py             # Orchestrator: scan + Jev bonds
│   │   ├── models/
│   │   │   └── graph.py               # Pydantic models (CodeFile, Symbol, etc.)
│   │   ├── services/
│   │   │   ├── analysis.py            # Q&A, impact, summaries
│   │   │   ├── jev_client.py          # TypeSafe Jev SDK wrapper (10 bonds)
│   │   │   ├── llm.py                 # Gemini/Ollama LLM client
│   │   │   └── neo4j_store.py         # Neo4j CRUD + graph queries
│   │   └── main.py                    # FastAPI app factory
│   ├── tests/                         # pytest test suite (94 tests)
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── CartographerApp.tsx     # Root workspace orchestrator
│   │   │   ├── layout.tsx             # Next.js root layout
│   │   │   └── page.tsx               # Entry page
│   │   ├── components/
│   │   │   ├── AskPanel.tsx           # AI Q&A panel
│   │   │   ├── CommandPalette.tsx      # Cmd+K command palette
│   │   │   ├── EmptyWorkspace.tsx      # Landing page / onboarding
│   │   │   ├── GraphPanel.tsx          # ReactFlow graph canvas
│   │   │   ├── GraphToolbar.tsx        # Graph controls + filters
│   │   │   ├── Inspector.tsx           # File detail inspector
│   │   │   ├── MarkdownView.tsx        # Markdown renderer
│   │   │   ├── NodeDetailDrawer.tsx    # Slide-over file detail
│   │   │   ├── RepositoryExplorer.tsx  # File tree + risk hotspots
│   │   │   ├── RiskBreakdown.tsx       # Risk bar chart
│   │   │   ├── RiskHotspots.tsx        # High-risk file list
│   │   │   ├── Toast.tsx              # Notification system
│   │   │   ├── WorkspaceTopbar.tsx     # Top navigation bar
│   │   │   └── *.test.tsx             # Component tests (20 files)
│   │   ├── lib/
│   │   │   └── api.ts                 # Typed API client + types
│   │   └── styles/
│   │       └── app.css                # Global stylesheet
│   ├── Dockerfile
│   ├── package.json
│   └── vitest.config.ts
├── docs/
│   └── architecture.md                # Technical architecture document
├── .github/workflows/
│   └── ci.yml                         # GitHub Actions CI pipeline
├── docker-compose.yml                 # Full-stack Docker orchestration
├── check.sh                           # Local quality gate script
├── .env.example                       # Environment variable template
└── LICENSE
```

---

## License

See [LICENSE](LICENSE) for details.
