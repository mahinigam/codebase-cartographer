# Solution Challenge Submission Notes

## Pitch

Codebase Cartographer is an AI-powered structural forensics tool for large software repositories. It builds a Neo4j knowledge graph from AST-derived code structure, dependency relationships, Git history, and risk signals, then uses Gemini to answer architectural questions with evidence.

## Impact

New developers often spend days reconstructing how a legacy codebase works. Architects struggle to identify fragile modules before refactors. Codebase Cartographer reduces that uncertainty by showing the actual structure, load-bearing files, and ripple effects of proposed changes.

## Demo Flow

1. Paste a local repository path.
2. Click Analyze.
3. Show files, symbols, imports, and load-bearing files.
4. Open the graph view.
5. Ask: "What are the riskiest parts of this codebase?"
6. Select a high-risk file and run impact analysis.
7. Explain how Gemini synthesizes answers from Neo4j graph retrieval.

## Free-First Design

- Neo4j Community runs locally through Docker.
- Gemini free API can be used as the primary AI layer.
- Ollama `qwen2.5-coder:7b` is supported as fallback.
- No paid cloud deployment is required.

## Security

- Secrets are loaded from `.env` and ignored by Git.
- Repository path restrictions can be enforced with `ALLOWED_REPO_ROOTS`.
- Answers include evidence so users can verify conclusions.

