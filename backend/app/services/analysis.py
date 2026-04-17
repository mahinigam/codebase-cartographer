from app.services.llm import llm_client
from app.services.neo4j_store import Neo4jStore


async def answer_architecture_question(store: Neo4jStore, question: str) -> dict:
    matches = store.search_files(question)
    context = "\n".join(
        f"- {item['path']} ({item['language']}), symbols={item['symbols']}, "
        f"risk={item['load_bearing_score']}"
        for item in matches
    )
    prompt = f"""
You are Codebase Cartographer, a structural forensics assistant.
Answer the developer's architecture question using only the retrieved graph context.
Be precise, cite file paths, and say when evidence is incomplete.

Question:
{question}

Retrieved graph context:
{context or "No direct path matches were found."}
"""
    answer = await llm_client.complete(prompt)
    return {"answer": answer, "evidence": matches}


async def explain_impact(store: Neo4jStore, path: str, depth: int) -> dict:
    impact = store.impact_for_file(path, depth)
    prompt = f"""
Explain the change impact for file {path}.
Use the dependency results below. Mention direct and transitive dependents,
and give a concise risk assessment for a refactor.

Impact data:
{impact}
"""
    impact["explanation"] = await llm_client.complete(prompt)
    return impact

