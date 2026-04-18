from fastapi import APIRouter, HTTPException

from app.indexing.scanner import UnsafeRepositoryPath, scan_repository
from app.models.graph import ImpactRequest, QueryRequest, ScanRequest
from app.services.analysis import answer_architecture_question, explain_impact
from app.services.neo4j_store import neo4j_store

router = APIRouter()


@router.get("/health")
def health() -> dict:
    neo4j_ok = False
    try:
        with neo4j_store() as store:
            neo4j_ok = store.ping()
    except Exception:
        neo4j_ok = False
    return {"ok": True, "neo4j": neo4j_ok}


@router.post("/scan")
def scan(request: ScanRequest) -> dict:
    try:
        graph = scan_repository(request.path)
    except UnsafeRepositoryPath as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with neo4j_store() as store:
        store.upsert_repository_graph(graph)
        overview = store.overview(repo_path=graph.root_path)
    return {
        "repository": graph.name,
        "root_path": graph.root_path,
        "files": len(graph.files),
        "symbols": len(graph.symbols),
        "imports": len(graph.imports),
        "overview": overview,
    }


@router.get("/overview")
def overview(repo_path: str | None = None) -> dict:
    with neo4j_store() as store:
        return {
            "overview": store.overview(repo_path=repo_path),
            "load_bearing": store.top_load_bearing_files(repo_path=repo_path),
        }


@router.get("/repositories")
def repositories() -> dict:
    with neo4j_store() as store:
        return {"repositories": store.repositories()}


@router.get("/graph")
def graph(limit: int = 80, repo_path: str | None = None) -> dict:
    with neo4j_store() as store:
        return store.graph_slice(limit=limit, repo_path=repo_path)


@router.post("/query")
async def query(request: QueryRequest) -> dict:
    with neo4j_store() as store:
        return await answer_architecture_question(store, request.question, request.repo_path)


@router.post("/impact")
async def impact(request: ImpactRequest) -> dict:
    with neo4j_store() as store:
        return await explain_impact(store, request.path, request.depth, request.repo_path)
