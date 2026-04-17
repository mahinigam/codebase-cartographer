# Codebase Cartographer

Codebase Cartographer is a structural forensics engine for legacy repositories. It turns a codebase into a navigable Neo4j knowledge graph of files, symbols, dependencies, Git history, risk signals, and AI-generated architectural summaries.

Instead of treating code as plain text, it combines deterministic static analysis with Gemini-powered reasoning and a local Ollama fallback.

## Why It Matters

Large codebases are hard to change safely because their real architecture is usually hidden in imports, call paths, historical patches, and undocumented conventions. Codebase Cartographer helps new joiners and senior architects answer:

- Where does this behavior live?
- Which files are load-bearing?
- What might break if I change this function?
- What does the module/package/repo actually do?
- Which parts of the codebase are isolated enough to refactor?

## Stack

- Frontend: React + Vite
- Backend: FastAPI
- Graph database: Neo4j Community
- Static analysis: Python AST, JS/TS structural extraction, Tree-sitter-ready design
- AI: Gemini free API primary, Ollama `qwen2.5-coder:7b` fallback
- Git intelligence: local Git history mining
- Tests: pytest + Vitest

## Quick Start

1. Copy env config:

```bash
cp .env.example .env
```

2. Add your Gemini API key to `.env`. If your key was shared anywhere public, rotate it first.

3. Start Neo4j:

```bash
docker compose up -d neo4j
```

4. Start backend:

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

5. Start frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Security Notes

- API keys are read from environment variables only.
- Repo paths are constrained by `ALLOWED_REPO_ROOTS` when configured.
- `.env` files are ignored by Git.
- The app indexes local source files and does not upload code unless an external LLM provider is enabled.

## Challenge Positioning

Built for Solution Challenge 2026 - Build with AI: a free-first, privacy-conscious AI tool that uses Google Gemini as the reasoning layer over deterministic software structure.

