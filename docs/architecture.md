# Architecture

Codebase Cartographer is built around structural forensics: deterministic code structure first, AI synthesis second.

```mermaid
flowchart TD
    A["Local repository"] --> B["Scanner"]
    B --> C["Python AST parser"]
    B --> D["Tree-sitter JS/TS parser"]
    B --> E["Git history miner"]
    C --> F["Risk scorer"]
    D --> F
    E --> F
    F --> G["Neo4j knowledge graph"]
    G --> H["File summaries + embeddings"]
    G --> I["Forensics dashboard"]
    G --> J["Impact analysis"]
    G --> K["Graph + vector retrieval"]
    K --> L["Gemini primary / Ollama fallback"]
    L --> M["Cited architectural answer"]
```

## Knowledge Graph

Core node types:

- `Repository`
- `File`
- `Symbol`
- `ExternalDependency`
- `Summary`

Core relationships:

- `Repository CONTAINS File`
- `File DEFINES Symbol`
- `File IMPORTS File`
- `File DEPENDS_ON ExternalDependency`
- `File SUMMARIZES Summary`

## Risk Model

The initial load-bearing score combines:

- fan-in: how many files depend on a file
- complexity: branch-heavy code is harder to change safely
- churn: files changed frequently in Git history carry more uncertainty
- fan-out: files that know many dependencies can spread coupling

The score is explainable and intentionally deterministic. AI may describe the risk, but it does not invent the score.

## AI Strategy

Gemini is the primary reasoning layer for its strong code understanding and free-tier availability. Ollama is a local fallback for offline use and private codebases.

When summaries are enabled, Cartographer sends truncated source snippets (default: 4,000 characters per file, up to 120 files) to the active LLM provider. Disable summaries or use Ollama-only for confidential repositories.

No API key is stored in source control.

## Persistence

Repository graphs are written to Neo4j in batched `UNWIND` statements. Each scan still rebuilds symbols and dependency edges for the repository, and removes File nodes that no longer exist on disk.

The architecture graph view returns the highest load-bearing files first, with a hard cap (400 nodes / 2,000 edges) so the UI stays usable on large repositories. Truncation is reported to the client so the missing remainder is visible.

