from app.services.llm import llm_client
from app.services.neo4j_store import Neo4jStore


async def answer_architecture_question(
    store: Neo4jStore, question: str, repo_path: str | None = None
) -> dict:
    matches = store.search_files(question, repo_path=repo_path)
    context = "\n".join(
        f"- {item['path']} ({item['language']}), symbols={item['symbols']}, "
        f"imports={item['imports']}, dependents={item['dependents']}, "
        f"external_deps={item['external_deps']}, risk={item['load_bearing_score']}, "
        f"matched={item['matched_words']}"
        for item in matches
    )
    prompt = f"""
You are Codebase Cartographer, a structural forensics assistant.
Answer the developer's architecture question using only the retrieved graph context.
Be precise, cite file paths, and say when evidence is incomplete.

Question:
{question}

Repository scope:
{repo_path or "all indexed repositories"}

Retrieved graph context:
{context or "No direct path matches were found."}
"""
    answer = await llm_client.complete(prompt)
    if answer.startswith("AI provider unavailable"):
        answer = _evidence_summary(question, matches)
    return {"answer": answer, "evidence": matches}


async def explain_impact(
    store: Neo4jStore, path: str, depth: int, repo_path: str | None = None
) -> dict:
    impact = store.impact_for_file(path, depth, repo_path=repo_path)
    prompt = f"""
Explain the change impact for file {path}.
Use the dependency results below. Mention direct and transitive dependents,
and give a concise risk assessment for a refactor.

Impact data:
{impact}
"""
    impact["explanation"] = await llm_client.complete(prompt)
    return impact


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
