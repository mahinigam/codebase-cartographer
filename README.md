# Codebase Cartographer

Codebase Cartographer is a structural forensics engine and interactive mapping tool for software repositories. It transforms any codebase into a highly navigable Neo4j knowledge graph of files, symbols, dependencies, Git history, risk signals, and AI-generated architectural summaries.

By moving beyond simple text search and syntax highlighting, Cartographer combines deterministic static analysis with Gemini-powered reasoning (and a local Ollama fallback) to expose the true architecture hidden within your code.

## Why It Matters

Large codebases are notoriously difficult to change safely because their real architecture is often obscured by complex import trees, historical patches, and undocumented conventions. Codebase Cartographer provides engineers and architects with a professional instrument to answer critical questions:

- Where does this specific behavior live?
- Which files are structurally load-bearing?
- What might break if I refactor this file?
- What does this undocumented module actually do?
- Which parts of the codebase are isolated enough to be safely extracted?

## Architecture & Features

### The Cartographer Map Engine
- **3-Column "Pro Tool" Interface**: Modeled after industry-standard creative and engineering tools, providing a dedicated workspace for repository management, an isolated central map canvas, and a dedicated right-hand inspector for analysis tools.
- **Interactive Infinite Canvas**: Powered by ReactFlow, the center stage provides a full-bleed, hardware-accelerated interactive map. Seamlessly pan and zoom through your codebase architecture with trackpad gestures.
- **Glassmorphic MiniMap**: Instantly locate high-risk clusters across massive repositories using the real-time radar MiniMap.

### Core Analysis Engine
- **Knowledge Graph**: Files, symbols, imports, and external dependencies are securely modeled and stored in a local Neo4j database.
- **Incremental Rescans**: Intelligent hashing reuses unchanged file fingerprints from Neo4j to avoid reparsing stable files, ensuring lightning-fast updates.
- **Risk Scoring**: Calculates a deterministic "load-bearing" score combining fan-in, AST complexity, Git churn, and fan-out.
- **Git History Mining**: Extracts churn counts and recency metrics directly from the local `.git` directory.

### AI & Semantic Analysis
- **Ask Cartographer**: Ask high-level architecture questions and receive answers grounded entirely in graph topology and vector evidence.
- **Impact Analysis**: Visually trace the direct and transitive dependents of any file to assess refactor risk before you write a line of code.
- **Semantic Search**: Gemini embeddings (stored in a Neo4j vector index) enable meaning-based, rather than keyword-based, file retrieval.

## Technology Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js (App Router) + React 19 + TypeScript |
| **Backend** | FastAPI (Python 3.12+) managed via `uv` |
| **Graph Database** | Neo4j Community Edition |
| **Static Analysis** | Python AST, Tree-sitter (JS/TS) |
| **AI (Primary)** | Google Gemini API |
| **AI (Fallback)** | Ollama `qwen2.5-coder:7b` |
| **Embeddings** | Gemini `text-embedding-004` / Ollama `nomic-embed-text` |
| **Graph Visualization** | ReactFlow + Dagre |

## Quick Start

1. **Configure Environment:**
```bash
cp .env.example .env
```
Add your Gemini API key and Neo4j credentials to `.env`.

2. **Start Neo4j Database:**
```bash
docker compose up -d neo4j
```

3. **Start the FastAPI Backend:**
```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

4. **Start the Next.js Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Open your browser to `http://localhost:3000`.

## Docker Compose

To run the entire stack in an isolated environment:

```bash
docker compose up --build
```

*Note: The backend container mounts the repository at `/workspace` for scanning. If using Ollama, it must be running on the host machine; Docker will connect via `http://host.docker.internal:11434`.*

## Usage Workflow

1. Paste an absolute local repository path into the Left Sidebar and click **Analyze**.
2. The engine will extract files, symbols, imports, and Git history into the Neo4j graph.
3. Click **Generate Summaries** to asynchronously create AI-powered file summaries and embeddings.
4. **Explore the Map**: Use your trackpad to zoom and pan the ReactFlow canvas. Click any node to open the **File Detail Drawer**.
5. **Ask Cartographer**: Query the graph with natural language using the Right Inspector.
6. **Impact Analysis**: Select a node on the map and run a Trace in the Right Inspector to highlight the dependency ripple effect.

## Security & Privacy

- **Local First**: The application indexes local source files and does not upload raw code unless an external LLM provider is explicitly enabled.
- **Provider Fallbacks**: When AI summaries are enabled, up to 4,000 characters of each file's source are sent to the Gemini API. To ensure absolute privacy for proprietary code, disable Gemini and rely entirely on the local Ollama fallback.
- **Path Constraints**: Summary generation automatically refuses paths that resolve outside the scanned repository root.
- **API Security**: `SCAN_MAX_FILES` and `SCAN_RATE_LIMIT_PER_MINUTE` cap expensive scan/summarization requests to prevent abuse in shared environments.
