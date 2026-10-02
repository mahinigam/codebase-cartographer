# Codebase Cartographer

**Structural forensics and code-intelligence infrastructure for understanding software repositories.**

Codebase Cartographer turns a source repository into an **interactive knowledge graph of files, symbols, dependencies, Git history, structural risk, and semantic evidence**.

It combines deterministic static analysis, graph reasoning, structured AI decisions, vector retrieval, and generative reasoning into a single investigation workflow.

> **Understand the architecture before you change the code.**

---

## Why Codebase Cartographer?

A large repository does not come with a reliable architectural map.

The important relationships are distributed across imports, dependency chains, historical changes, shared utilities, undocumented modules, and patterns that only become obvious when many signals are considered together.

Cartographer is built around a simple idea:

**Software architecture should be derived from evidence, not guessed from filenames or generated from an LLM alone.**

It helps answer questions such as:

- **Where does this behavior actually live?**
- **Which files are structurally load-bearing?**
- **What is likely to be affected if I change this module?**
- **Which parts of the repository are tightly coupled?**
- **Does this file appear to be test code, infrastructure, UI, or business logic?**
- **Which modules deserve architectural attention first?**
- **What does an unfamiliar file appear to do?**
- **Can I investigate the repository conversationally without losing the underlying evidence?**

---

## What It Does

Cartographer performs a multi-stage analysis of a repository:

```text
Repository
    │
    ▼
File Discovery
    │
    ├── Python AST analysis
    ├── JavaScript / TypeScript Tree-sitter analysis
    └── Git history mining
    │
    ▼
Dependency Resolution
    │
    ▼
Deterministic Structural Analysis
    │
    ├── Fan-in / fan-out
    ├── Complexity
    ├── Churn
    └── Load-bearing risk
    │
    ▼
Structured AI Analysis (Jev)
    │
    ├── Architectural role
    ├── Test detection
    ├── Framework detection
    ├── Semantic risk
    ├── Dead-code candidates
    ├── Query routing
    ├── Cluster assessment
    └── Refactor safety
    │
    ▼
Neo4j Knowledge Graph
    │
    ├── Files
    ├── Symbols
    ├── Import edges
    ├── External dependencies
    └── AI-generated summaries + embeddings
    │
    ▼
Investigation Layer
    │
    ├── Interactive dependency map
    ├── Risk hotspots
    ├── File inspector
    ├── Natural-language architecture Q&A
    └── Change-impact analysis
```

The important design decision is that **AI is not the foundation of the system**.

The repository is first converted into deterministic structural evidence. AI then enriches, classifies, prioritizes, and explains that evidence.

---

# Core Capabilities

## 1. Repository Mapping

Cartographer builds a navigable graph of the repository rather than treating the codebase as a collection of independent files.

The graph captures:

- repositories
- source files
- functions and classes
- internal imports
- external dependencies
- AI-generated file summaries
- semantic embeddings
- structural metrics
- Git history signals
- AI-derived architectural metadata

The graph is persisted in Neo4j and can be queried independently of the generative AI layer.

---

## 2. Static Code Analysis

### Python

Python repositories are parsed with the standard `ast` module.

Cartographer extracts:

- classes
- functions
- async functions
- imports
- `from ... import ...` statements
- line ranges
- symbol signatures
- cyclomatic-style structural complexity

### JavaScript / TypeScript

JavaScript and TypeScript are analyzed using Tree-sitter, with a regex fallback for parser failures or environments where Tree-sitter is unavailable.

The parser recognizes common:

- ES module imports
- CommonJS `require()`
- functions
- arrow functions
- classes
- control-flow constructs used in complexity estimation

This gives the system a language-aware structural representation before any AI analysis occurs.

---

## 3. Dependency Resolution

Import statements are normalized into actual repository relationships where possible.

### Python

The resolver handles common:

- dotted module imports
- relative imports
- package-style modules
- `__init__.py` aliases

### JavaScript / TypeScript

The resolver handles common:

- relative imports
- extensionless modules
- `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, `.cjs`
- `/index` conventions

Resolved dependencies become graph edges:

```text
File A ──IMPORTS──▶ File B
```

Unresolved imports are retained as external dependencies:

```text
File A ──DEPENDS_ON──▶ "package-name"
```

This distinction allows Cartographer to reason separately about **internal architecture** and **external coupling**.

---

# Structural Risk Engine

One of the project's central design choices is that structural risk is not delegated entirely to an LLM.

Cartographer first calculates a deterministic load-bearing score from repository evidence.

```text
Risk =
    45% × normalized fan-in
  + 25% × normalized complexity
  + 20% × normalized churn
  + 10% × normalized fan-out
```

High fan-in indicates that many modules depend on a file.

Complexity captures structural branching.

Git churn approximates how actively the file changes.

Fan-out captures how broadly the module itself depends on other modules.

### Trivial-file damping

A highly reused utility should not automatically outrank a genuinely complex architectural module.

For small, simple files, fan-in is therefore dampened before the final score is calculated.

### Semantic enhancement

Files with meaningful deterministic risk can then be evaluated by the structured AI layer.

The semantic score is blended with the deterministic score rather than replacing it.

This produces a **hybrid structural + semantic risk model**.

---

# Two-Tier AI Architecture

Cartographer deliberately separates **decision-making** from **generative reasoning**.

## System One — TypeSafe Jev

Jev acts as the structured decision engine.

It provides categorical, probabilistic, and numeric decisions instead of free-form prose.

The current integration covers ten analysis bonds.

| Bond | Purpose |
|---|---|
| **File Classification** | Identify architectural role |
| **Semantic Risk** | Estimate semantic refactoring risk |
| **Test Detection** | Identify test/spec/fixture files |
| **Query Routing** | Decide how an architecture question should be answered |
| **Cluster Assessment** | Estimate cohesion, coupling, and extraction readiness |
| **Refactor Safety** | Estimate safety, blast radius, and strategy |
| **Summary Triage** | Prioritize files for expensive summarization |
| **Framework Detection** | Identify ecosystem and architectural layer |
| **Re-summarization Check** | Decide whether an existing summary is stale |
| **Dead Code Detection** | Evaluate zero-fan-in candidates |

This is useful because many repository-analysis tasks do **not** require a generative model.

For example:

```text
"What is this file's architectural role?"
```

can be treated as a structured classification problem.

Likewise:

```text
"Does this repository need a generated summary for this file?"
```

can be treated as a probability/priority decision.

The system does not need to spend a full generative request on every such task.

---

## System Two — Gemini / Ollama

The generative layer is reserved for tasks where natural-language reasoning adds real value.

It is used for:

### File Summaries

The system sends a bounded source snippet to the configured LLM provider and generates an architectural summary.

### Semantic Retrieval

Generated summaries can be embedded and stored in Neo4j's vector index.

### Architecture Q&A

Questions can combine:

```text
graph evidence
+
semantic retrieval
+
generative reasoning
```

rather than relying exclusively on the model's internal knowledge.

### Impact Narratives

Dependency results are passed to the generative layer to produce a readable explanation of change impact.

---

## Graceful AI Degradation

AI is treated as an enhancement layer rather than a hard dependency.

The generative cascade is:

```text
Gemini
   ↓ unavailable
Ollama
   ↓ unavailable
Deterministic graph-based fallback
```

This means the structural analysis system can still provide useful repository information even when external generative services are unavailable.

---

# Incremental Scanning

Cartographer does not need to fully re-parse every repository on every scan.

For indexed repositories, the scanner can reuse cached state from Neo4j.

It compares:

- file size
- modification timestamp
- SHA-256 content fingerprint

Unchanged files can reuse cached:

- symbol information
- import edges
- structural metadata

This gives the scanner an incremental execution path instead of treating every rescan as a clean rebuild.

---

# Git History as an Architectural Signal

Static structure alone does not tell the full story.

Cartographer also mines Git history and tracks:

- file churn
- last modification information

The current implementation examines recent commit history and uses churn as one of the structural signals in the risk model.

This creates a useful distinction:

```text
How connected is this file?
+
How complex is it?
+
How frequently does it change?
=
How much architectural attention does it deserve?
```

---

# Knowledge Graph

Neo4j is the persistence layer for the repository model.

## Graph Schema

```text
Repository
    │
    └── CONTAINS ──▶ File
                         │
                         ├── DEFINES ──▶ Symbol
                         │
                         ├── IMPORTS ──▶ File
                         │
                         ├── DEPENDS_ON ──▶ ExternalDependency
                         │
                         └── SUMMARIZES ──▶ Summary
```

### Node types

| Node | Purpose |
|---|---|
| `Repository` | Repository identity and scan metadata |
| `File` | Source file and structural metadata |
| `Symbol` | Functions, classes, and related symbols |
| `ExternalDependency` | Unresolved third-party dependencies |
| `Summary` | AI-generated summary plus embedding metadata |

### Why a graph?

Because repository questions are inherently relational.

For example:

```text
What depends on `neo4j_store.py`?
```

is a graph traversal.

So is:

```text
What is the transitive impact of changing `analysis.py`?
```

and:

```text
Which modules form a tightly connected architectural cluster?
```

A graph database gives these relationships a native representation instead of reconstructing them from flat JSON every time.

---

# Semantic Retrieval

Generated summaries can be embedded and indexed in Neo4j.

This allows architecture questions to combine two evidence sources:

### Structural evidence

```text
imports
dependents
symbols
risk
complexity
churn
```

### Semantic evidence

```text
vector similarity
+
AI-generated summaries
```

The resulting architecture assistant is therefore grounded in both:

**what the graph says**

and

**what the code appears to mean**.

---

# Architecture Questions

The `/api/query` pipeline uses structured routing before deciding how much generative reasoning is necessary.

Conceptually:

```text
User Question
      │
      ▼
Jev Query Router
      │
      ├── File navigation ───────▶ graph search
      │
      ├── Risk question ─────────▶ structural risk data
      │
      ├── Dependency question ──▶ graph traversal
      │
      └── Complex question ──────▶
                  │
                  ├── graph retrieval
                  ├── semantic retrieval
                  └── Gemini / Ollama
```

This lets simple questions take a cheaper structural path while complex questions can use deeper reasoning.

---

# Impact Analysis

One of the most useful workflows is change-impact investigation.

Given a target file, Cartographer can determine:

- direct dependents
- transitive dependents
- traversal depth
- structural blast radius

The system then applies the refactor-safety decision layer and can generate a human-readable explanation.

Conceptually:

```text
Target File
    │
    ▼
Dependency Traversal
    │
    ├── Direct dependents
    └── Transitive dependents
            │
            ▼
     Refactor Safety
            │
            ├── safety probability
            ├── blast radius
            └── suggested strategy
            │
            ▼
       AI explanation
```

This turns the graph from a visualization into an **engineering investigation tool**.

---

# Interactive Investigation Workspace

The frontend is designed around investigation rather than dashboards.

## Repository Explorer

Browse:

- repositories
- files
- architecture views
- risk hotspots

## Graph Canvas

ReactFlow renders the repository topology using a Dagre layout.

The graph supports:

- pan
- zoom
- node selection
- dependency highlighting
- risk-oriented filtering
- test-file filtering
- isolated-node filtering
- bounded graph slices for large repositories

## Inspector

Selecting a file opens detailed evidence including:

- structural risk
- risk components
- symbols
- imports
- dependents
- external dependencies
- architectural role
- framework
- semantic risk category
- dead-code signal
- AI summary
- impact analysis

## Command Palette

`Cmd+K` provides a fast entry point for:

- repository search
- file lookup
- symbol lookup
- architecture questions

## Ask Cartographer

Natural-language queries return Markdown responses with supporting evidence that can be used to navigate back into the repository.

---

# Example Investigation Workflow

A typical session looks like this:

```text
1. Analyze repository
        ↓
2. Build structural graph
        ↓
3. Inspect architecture / risk hotspots
        ↓
4. Select a suspicious or important file
        ↓
5. Inspect symbols + dependencies + risk
        ↓
6. Trace impact
        ↓
7. Ask an architectural question
        ↓
8. Inspect supporting evidence
        ↓
9. Decide how to approach the change
```

The system is designed to keep the engineer close to the underlying evidence throughout the process.

---

# Technology Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 16 · React 19 · TypeScript |
| **Backend** | FastAPI · Python · `uv` |
| **Graph Database** | Neo4j 5 Community Edition |
| **Python Analysis** | Python `ast` |
| **JS/TS Analysis** | Tree-sitter + regex fallback |
| **Git Analysis** | GitPython |
| **Structured AI** | TypeSafe AI / Jev |
| **Generative AI** | Google Gemini · Ollama fallback |
| **Embeddings** | Gemini / Ollama fallback |
| **Graph Visualization** | ReactFlow · Dagre |
| **UI** | `react-resizable-panels` · `lucide-react` · React Markdown |
| **Backend Testing** | pytest · pytest-asyncio · pytest-cov |
| **Frontend Testing** | Vitest · Testing Library |
| **Static Checks** | Ruff · mypy · TypeScript |
| **CI** | GitHub Actions |
| **Containerization** | Docker Compose |

---

# API Surface

All endpoints are exposed beneath `/api`.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | API + Neo4j health status |
| `POST` | `/api/scan` | Scan or incrementally rescan a repository |
| `GET` | `/api/overview` | Repository statistics + load-bearing files |
| `GET` | `/api/repositories` | Indexed repositories |
| `GET` | `/api/files` | Indexed file metadata |
| `GET` | `/api/graph` | Bounded graph slice + architectural clusters |
| `GET` | `/api/search` | Keyword file/symbol/dependency search |
| `POST` | `/api/query` | Architecture Q&A |
| `POST` | `/api/impact` | Dependency impact analysis |
| `GET` | `/api/file-detail` | Detailed file inspection |
| `POST` | `/api/summaries` | AI summary generation |

---

# Security & Privacy

Cartographer is designed around a local-first workflow.

### Repository boundaries

`ALLOWED_REPO_ROOTS` can restrict which local paths are eligible for analysis.

### API authentication

When configured, `API_TOKEN` protects the API using either:

- Bearer authentication
- `X-API-Key`

### Resource controls

The backend provides configurable limits for:

- repository file count
- scan request frequency
- graph node count
- graph edge count
- summary limits

### Source-code handling

The structural analysis itself operates on local repository files.

External model providers are only involved when those providers are enabled.

Generative summarization uses bounded source snippets rather than automatically sending entire repositories.

For environments requiring stronger privacy guarantees, Ollama can be used as the local generative fallback.

---

# Incremental + Bounded by Design

Large repositories introduce two practical problems:

**recomputation** and **visual overload**.

Cartographer addresses both.

### Incremental scanning

Reuse previously indexed information when files have not changed.

### Bounded graph slices

The API deliberately returns a limited graph slice rather than forcing the browser to render every repository node simultaneously.

### Selective AI work

Jev can triage files and route queries so expensive generative calls are used where they provide the most value.

These three mechanisms work together to keep the system practical as repository size increases.

---

# Development & Testing

The project includes backend and frontend test suites covering core indexing, graph, API, analysis, and UI behavior.

### Backend

- pytest
- pytest-asyncio
- pytest-cov
- Ruff
- mypy

The backend test suite is configured with a **90% coverage floor**.

### Frontend

- Vitest
- React Testing Library
- V8 coverage
- TypeScript checking

The frontend coverage configuration targets **85% coverage across lines, functions, branches, and statements**.

### Run local checks

```bash
bash ./check.sh
```

### Continuous Integration

GitHub Actions runs the repository's automated test and validation workflow for changes to `main` and pull requests.

---

# Docker

The repository can run as a three-service stack:

```text
┌───────────────────────────┐
│         Frontend          │
│       Next.js / React     │
│         :5173             │
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│          Backend          │
│        FastAPI            │
│          :8000            │
└─────────────┬─────────────┘
              │
              ▼
┌───────────────────────────┐
│          Neo4j            │
│    Graph + Vector Index   │
│      :7474 / :7687       │
└───────────────────────────┘
```

Ollama can optionally run on the host and provide local generation/embedding fallback support.

---

# Quick Start

## Prerequisites

- Docker / Docker Compose
- Python 3.12+
- `uv`
- Node.js 22+
- npm

## 1. Configure environment

```bash
cp .env.example .env
```

Configure the providers you intend to use.

At minimum, local development requires Neo4j credentials. AI features require the corresponding provider credentials or a local Ollama setup.

## 2. Start Neo4j

```bash
docker compose up -d neo4j
```

## 3. Start the backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

## 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

---

# Full Docker Startup

To start the complete stack:

```bash
docker compose up --build
```

The stack exposes:

| Service | Port |
|---|---:|
| Frontend | `5173` |
| Backend | `8000` |
| Neo4j Browser | `7474` |
| Neo4j Bolt | `7687` |

For anything beyond local development, replace the example Neo4j credentials and configure the relevant authentication and path restrictions.

---

# Repository Structure

```text
codebase-cartographer/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py
│   │   │
│   │   ├── core/
│   │   │   └── config.py
│   │   │
│   │   ├── indexing/
│   │   │   ├── discovery.py
│   │   │   ├── git_history.py
│   │   │   ├── js_parser.py
│   │   │   ├── python_parser.py
│   │   │   └── scanner.py
│   │   │
│   │   ├── models/
│   │   │   └── graph.py
│   │   │
│   │   ├── services/
│   │   │   ├── analysis.py
│   │   │   ├── jev_client.py
│   │   │   ├── llm.py
│   │   │   └── neo4j_store.py
│   │   │
│   │   └── main.py
│   │
│   └── tests/
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── lib/
│   │   └── styles/
│   │
│   ├── package.json
│   └── vitest.config.ts
│
├── docs/
│   └── architecture.md
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── docker-compose.yml
├── check.sh
├── .env.example
└── LICENSE
```

---

# Engineering Principles

The architecture is built around a few deliberate principles.

### 1. Evidence before generation

The graph and deterministic analysis establish the repository facts before generative reasoning is invoked.

### 2. Structured decisions before free-form prose

Classification, routing, prioritization, and risk decisions are treated as structured problems.

### 3. AI as an augmentation layer

The system remains useful when generative AI is unavailable.

### 4. Incremental work over brute-force recomputation

Unchanged files can reuse indexed state.

### 5. Investigation over dashboarding

The interface is organized around tracing relationships and understanding changes, not merely displaying repository statistics.

### 6. Bounded complexity

Graph responses, source snippets, scan counts, and expensive AI calls are all bounded to keep the system practical.

---

# Scope & Limitations

Cartographer is intentionally a **structural code-intelligence system**, not a full compiler or language-server implementation.

The current analyzers focus on Python, JavaScript, and TypeScript and resolve common repository import patterns.

Likewise, dead-code detection is probabilistic: zero fan-in identifies candidates, but the system does not formally prove that a file is unreachable in every runtime or deployment configuration.

Risk scores are decision-support signals, not guarantees.

The objective is to provide engineers with **useful architectural evidence and investigative context**, not to replace human code review.

---

# Why This Architecture?

The central design decision can be summarized as:

```text
Static structure
      +
Git history
      +
Graph relationships
      +
Structured AI decisions
      +
Semantic retrieval
      +
Generative reasoning
      ↓
Interactive code intelligence
```

Each layer contributes something different.

Static analysis provides facts.

Git provides historical context.

Neo4j provides relationships.

Structured AI provides classification and probabilistic decisions.

Vector search provides semantic retrieval.

Generative AI provides explanations.

The interface turns all of that into something an engineer can actually investigate.

---

# Further Documentation

For the deeper implementation architecture, see:

- [`docs/architecture.md`](docs/architecture.md)
- [`backend/app/indexing/scanner.py`](backend/app/indexing/scanner.py)
- [`backend/app/services/neo4j_store.py`](backend/app/services/neo4j_store.py)
- [`backend/app/services/jev_client.py`](backend/app/services/jev_client.py)
- [`backend/app/services/analysis.py`](backend/app/services/analysis.py)

---

# License

See [`LICENSE`](LICENSE).
