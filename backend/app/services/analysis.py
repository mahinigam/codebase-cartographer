import asyncio
from pathlib import Path

from app.core.config import settings
from app.services.llm import llm_client
from app.services.neo4j_store import Neo4jStore


async def answer_architecture_question(
    store: Neo4jStore, question: str, repo_path: str | None = None
) -> dict:
    matches = store.search_files(question, repo_path=repo_path)
    if not matches and _asks_about_risk(question):
        matches = _load_bearing_matches(store, repo_path)
    semantic_matches = []
    embedding = await llm_client.embed(question, task="RETRIEVAL_QUERY")
    if embedding:
        semantic_matches = store.semantic_search(embedding, repo_path=repo_path)
    context = "\n".join(
        f"- {item['path']} ({item['language']}), symbols={item['symbols']}, "
        f"imports={item['imports']}, dependents={item['dependents']}, "
        f"external_deps={item['external_deps']}, risk={item['load_bearing_score']}, "
        f"matched={item['matched_words']}"
        for item in matches
    )
    semantic_context = "\n".join(
        f"- {item['path']} (score={item['score']:.3f})\n  {item['summary']}"
        for item in semantic_matches
    )
    prompt = f"""
You are Codebase Cartographer, a structural forensics AI assistant.
Answer the developer's architecture question using the retrieved graph and summary context.

Please format your response in pristine Markdown:
- Use clear headings (`###`) to structure your answer.
- Use bullet points for lists of files, symbols, or dependencies.
- Use inline code formatting (`like this`) for file paths, variable names, and code symbols.
- Be precise and insightful. Cite file paths explicitly.
- Clearly state if the provided evidence is incomplete or if you are inferring relationships
  not present in the context.

Question:
{question}

Repository scope:
{repo_path or "all indexed repositories"}

Retrieved graph context:
{context or "No direct path matches were found."}

Semantic summary context:
{semantic_context or "No semantic summaries were retrieved."}
"""
    answer = await llm_client.complete(prompt)
    if answer.startswith("AI provider unavailable"):
        answer = _evidence_summary(question, matches)
    return {"answer": answer, "evidence": matches, "semantic_matches": semantic_matches}


def _asks_about_risk(question: str) -> bool:
    cleaned = "".join(character.lower() if character.isalnum() else " " for character in question)
    words = cleaned.split()
    return bool(
        {
            "risk",
            "risks",
            "risky",
            "riskiest",
            "load",
            "bearing",
            "loadbearing",
            "critical",
            "fragile",
            "impact",
        }
        & set(words)
    )


def _load_bearing_matches(store: Neo4jStore, repo_path: str | None = None) -> list[dict]:
    return [
        {
            "path": item["path"],
            "language": item["language"],
            "symbols": [],
            "imports": [],
            "dependents": [],
            "external_deps": [],
            "load_bearing_score": item["load_bearing_score"],
            "matched_words": ["load-bearing", "risk"],
        }
        for item in store.top_load_bearing_files(repo_path=repo_path)
    ]


async def explain_impact(
    store: Neo4jStore, path: str, depth: int, repo_path: str | None = None
) -> dict:
    impact = store.impact_for_file(path, depth, repo_path=repo_path)
    prompt = f"""
You are Codebase Cartographer, a structural forensics AI assistant.
Explain the change impact for the file `{path}` based on the dependency results below.

Please format your response in pristine Markdown:
- Use clear headings (e.g., `### Direct Dependents`, `### Transitive Dependents`,
  `### Risk Assessment`).
- Use bullet points to list affected files and modules.
- Use inline code formatting (`like this`) for file paths.
- Provide a concise but comprehensive risk assessment for a refactor.

Impact data:
{impact}
"""
    impact["explanation"] = await llm_client.complete(prompt)
    return impact


async def generate_summaries_for_repo(
    store: Neo4jStore, repo_path: str, max_files: int | None = None
) -> dict:
    root = Path(repo_path)
    file_paths = store.file_paths(repo_path)
    if not file_paths:
        return {"requested": 0, "created": 0, "skipped": 0}

    limit = max_files or settings.summary_max_files
    target_paths = file_paths[:limit]
    semaphore = asyncio.Semaphore(3)
    result = {"requested": len(target_paths), "created": 0, "skipped": 0}
    lock = asyncio.Lock()

    async def process(path: str) -> None:
        async with semaphore:
            summary = await _summarize_file(root, path)
            if not summary:
                async with lock:
                    result["skipped"] += 1
                return
            embedding = await llm_client.embed(summary, task="RETRIEVAL_DOCUMENT")
            store.upsert_file_summary(
                repo_path=repo_path,
                file_path=path,
                summary_text=summary,
                embedding=embedding or None,
                model=_active_llm_model(),
                provider=_active_llm_provider(),
            )
            async with lock:
                result["created"] += 1

    await asyncio.gather(*(process(path) for path in target_paths))
    return result


def _active_llm_provider() -> str:
    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        return "gemini"
    if settings.fallback_llm_provider == "ollama":
        return "ollama"
    return "none"


def _active_llm_model() -> str:
    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        return settings.gemini_model
    if settings.fallback_llm_provider == "ollama":
        return settings.ollama_model
    return "none"


async def _summarize_file(root: Path, relative_path: str) -> str:
    repo_root = root.resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(repo_root) or not path.exists() or not path.is_file():
        return ""
    source = path.read_text(encoding="utf-8", errors="ignore")
    snippet = source[: settings.summary_max_chars]
    prompt = f"""
You are Codebase Cartographer. Summarize the file for architectural context.

Please format your summary as a pristine, concise Markdown paragraph.
Mention primary responsibilities, key symbols, and dependencies.
Use inline code formatting (`like this`) for symbols and file paths.
Use plain language and avoid speculation.

File: {relative_path}

Source (truncated):
{snippet}
"""
    summary = await llm_client.complete(prompt)
    return summary.strip()


def _evidence_summary(question: str, matches: list[dict]) -> str:
    if not matches:
        return (
            f"No graph evidence matched the question: {question}\n\n"
            "Try asking about a file name, symbol name, import, dependency, or architectural area."
        )

    lines = [
        f"Graph evidence for: {question}",
        "",
        "The strongest matches are:",
    ]
    for item in matches[:6]:
        lines.extend(
            [
                f"- {item['path']} ({item['language']}, risk {item['load_bearing_score']})",
                f"  Symbols: {', '.join(item['symbols'][:6]) or 'none'}",
                f"  Imports: {', '.join(item['imports'][:4]) or 'none'}",
                f"  Dependents: {', '.join(item['dependents'][:4]) or 'none'}",
                f"  External deps: {', '.join(item['external_deps'][:4]) or 'none'}",
            ]
        )
    return "\n".join(lines)
