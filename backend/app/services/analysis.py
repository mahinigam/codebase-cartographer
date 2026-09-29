import asyncio
from pathlib import Path

from app.core.config import settings
from app.services.llm import llm_client
from app.services.neo4j_store import Neo4jStore
from app.services.jev_client import jev_client


async def answer_architecture_question(
    store: Neo4jStore, question: str, repo_path: str | None = None
) -> dict:
    # ── Bond 4: Smart query routing via Jev ──
    route_result = await jev_client.route_query(question)

    if route_result:
        intent = route_result.get("intent")
        needs_ai = route_result.get("needs_ai_generation")
        intent_name = intent.answer if intent else "general-ai-question"
        skip_gemini = needs_ai and needs_ai.probability is not None and needs_ai.probability < 0.4

        # Fast paths that don't need Gemini
        if intent_name == "navigate-to-file" or (intent_name == "symbol-lookup" and skip_gemini):
            matches = store.search_files(question, repo_path=repo_path)
            return {
                "answer": _evidence_summary(question, matches),
                "evidence": matches,
                "semantic_matches": [],
                "routed_intent": intent_name,
            }

        if intent_name == "risk-assessment" and skip_gemini:
            load_bearing = _load_bearing_matches(store, repo_path)
            lines = ["### Riskiest Files\n"]
            for item in load_bearing[:10]:
                lines.append(
                    f"- `{item['path']}` — risk score **{item['load_bearing_score']}**"
                )
            return {
                "answer": "\n".join(lines),
                "evidence": load_bearing,
                "semantic_matches": [],
                "routed_intent": intent_name,
            }

        if intent_name in ("dependency-trace-forward", "dependency-trace-reverse"):
            # Extract file path from question and redirect to impact
            matches = store.search_files(question, limit=1, repo_path=repo_path)
            if matches:
                target = matches[0]["path"]
                impact = store.impact_for_file(target, depth=3, repo_path=repo_path)
                if skip_gemini:
                    explanation = _format_impact_as_markdown(impact)
                else:
                    explanation = await _generate_impact_narrative(impact, target)
                return {
                    "answer": explanation,
                    "evidence": matches,
                    "semantic_matches": [],
                    "routed_intent": intent_name,
                }

    # ── Full pipeline (existing logic, unchanged) ──
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


def _format_impact_as_markdown(impact: dict) -> str:
    """Format impact data as Markdown without using Gemini."""
    lines = [f"### Impact Analysis for `{impact['target']}`\n"]
    direct = impact.get("direct_dependents", [])
    trans = impact.get("transitive_dependents", [])
    lines.append(f"**{len(direct)}** direct dependents, **{len(trans)}** transitive.\n")
    if direct:
        lines.append("#### Direct Dependents")
        for d in direct:
            lines.append(f"- `{d}`")
    if trans:
        lines.append("\n#### Transitive Dependents")
        for t in trans[:20]:
            path = t.get("path", t) if isinstance(t, dict) else t
            dist = t.get("distance", "?") if isinstance(t, dict) else "?"
            lines.append(f"- `{path}` (depth {dist})")
    return "\n".join(lines)


async def _generate_impact_narrative(impact: dict, target: str) -> str:
    """Generate Gemini narrative for impact (existing logic extracted)."""
    prompt = f"""
You are Codebase Cartographer, a structural forensics AI assistant.
Explain the change impact for the file `{target}` based on the dependency results below.

Please format your response in pristine Markdown:
- Use clear headings (e.g., `### Direct Dependents`, `### Transitive Dependents`,
  `### Risk Assessment`).
- Use bullet points to list affected files and modules.
- Use inline code formatting (`like this`) for file paths.
- Provide a concise but comprehensive risk assessment for a refactor.

Impact data:
{impact}
"""
    return await llm_client.complete(prompt)


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

    # ── Bond 6: Jev refactor safety gate ──
    file_detail = store.file_detail(path, repo_path=repo_path)
    safety_result = await jev_client.evaluate_refactor_safety(
        target_path=path,
        direct_dependents=impact.get("direct_dependents", []),
        transitive_dependents=impact.get("transitive_dependents", []),
        target_risk_score=file_detail.get("load_bearing_score", 0) if file_detail else 0,
        target_complexity=file_detail.get("complexity", 0) if file_detail else 0,
        target_loc=file_detail.get("loc", 0) if file_detail else 0,
    )

    if safety_result:
        safe_dec = safety_result.get("safe_to_refactor")
        strat_dec = safety_result.get("recommended_strategy")
        blast_dec = safety_result.get("estimated_blast_radius")
        impact["refactor_safety"] = {
            "safe_to_refactor": safe_dec.probability > 0.6 if safe_dec else None,
            "safe_probability": round(safe_dec.probability, 3) if safe_dec else None,
            "recommended_strategy": strat_dec.answer if strat_dec else None,
            "blast_radius": round(blast_dec.value, 1) if blast_dec else None,
        }

    # Existing Gemini narrative
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
        return {"requested": 0, "created": 0, "skipped": 0, "triaged_out": 0}

    limit = max_files or settings.summary_max_files

    # ── Bond 7: Triage files with Jev before spending Gemini calls ──
    triaged: list[tuple[str, float]] = []  # (path, priority)
    triaged_out = 0

    # Get file metadata for triage
    all_files = store.files_list(repo_path=repo_path)
    file_meta = {f["path"]: f for f in all_files}

    if jev_client.enabled:
        semaphore = asyncio.Semaphore(settings.jev_batch_concurrency)

        # Precompute fan_in from graph
        fan_in_map = _compute_fan_in(store, repo_path)

        async def triage_one(path: str) -> tuple[str, float, bool]:
            async with semaphore:
                meta = file_meta.get(path, {})
                snippet = ""
                try:
                    p = root / path
                    if p.exists():
                        snippet = p.read_text(encoding="utf-8", errors="ignore")[:1000]
                except Exception:
                    pass

                result = await jev_client.triage_for_summary(
                    file_path=path,
                    language=meta.get("language", ""),
                    loc=meta.get("loc", 0),
                    complexity=meta.get("complexity", 0),
                    fan_in=fan_in_map.get(path, 0),
                    fan_out=0,
                    symbols=[],
                    snippet=snippet,
                )
                if result:
                    needs = result.get("needs_summary")
                    priority = result.get("summary_priority")
                    should_summarize = needs.probability > 0.5 if needs else True
                    prio_val = priority.value if priority else 5.0
                    return (path, prio_val, should_summarize)
                return (path, 5.0, True)

        triage_results = await asyncio.gather(*(triage_one(p) for p in file_paths))
        for path, prio, should in triage_results:
            if should:
                triaged.append((path, prio))
            else:
                triaged_out += 1

        # Sort by priority descending
        triaged.sort(key=lambda x: -x[1])
        target_paths = [p for p, _ in triaged[:limit]]
    else:
        target_paths = file_paths[:limit]

    # Existing summarization logic
    semaphore_llm = asyncio.Semaphore(3)
    result = {
        "requested": len(target_paths),
        "created": 0,
        "skipped": 0,
        "triaged_out": triaged_out,
    }
    lock = asyncio.Lock()

    async def process(path: str) -> None:
        async with semaphore_llm:
            # ── Bond 9: Check if re-summarization is needed ──
            if jev_client.enabled:
                existing = store.get_existing_summary(repo_path, path)
                if existing and existing.get("text"):
                    meta = file_meta.get(path, {})
                    result_jev = await jev_client.should_resummarize(
                        file_path=path,
                        language=meta.get("language", ""),
                        old_loc=meta.get("loc", 0),
                        new_loc=meta.get("loc", 0),
                        old_complexity=meta.get("complexity", 0),
                        new_complexity=meta.get("complexity", 0),
                        old_content_hash="",
                        new_content_hash=meta.get("content_hash", ""),
                        existing_summary=existing["text"],
                    )
                    if result_jev:
                        needs = result_jev.get("needs_resummarize")
                        if needs and needs.probability is not None and needs.probability < 0.4:
                            async with lock:
                                result["skipped"] += 1
                            return

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


def _compute_fan_in(store: Neo4jStore, repo_path: str) -> dict[str, int]:
    """Helper to compute fan-in counts from Neo4j."""
    with store.driver.session() as session:
        res = session.run(
            """
            MATCH (r:Repository {root_path: $repo_path})-[:CONTAINS]->(f:File)
            OPTIONAL MATCH (dep:File)-[:IMPORTS]->(f)
            RETURN f.path AS path, count(dep) AS fan_in
            """,
            repo_path=repo_path,
        )
        return {r["path"]: r["fan_in"] for r in res}


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
