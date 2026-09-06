import logging

from fastapi import APIRouter, HTTPException, Query

from app.indexing.scanner import UnsafeRepositoryPath, scan_repository
from app.models.graph import ImpactRequest, QueryRequest, ScanRequest, SummaryRequest
from app.services.analysis import (
    answer_architecture_question,
    explain_impact,
    generate_summaries_for_repo,
)
from app.services.neo4j_store import (
    GRAPH_DEFAULT_EDGE_LIMIT,
    GRAPH_DEFAULT_NODE_LIMIT,
    GRAPH_MAX_EDGE_LIMIT,
    GRAPH_MAX_NODE_LIMIT,
    neo4j_store,
)

router = APIRouter()
logger = logging.getLogger(__name__)


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
async def scan(request: ScanRequest) -> dict:
    try:
        graph = scan_repository(request.path)
    except UnsafeRepositoryPath as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with neo4j_store() as store:
        store.upsert_repository_graph(graph)
        overview = store.overview(repo_path=graph.root_path)
        summary_status = None
        if request.summarize:
            try:
                summary_status = await generate_summaries_for_repo(store, graph.root_path)
            except Exception as exc:
                logger.exception("Summary generation failed after scan")
                summary_status = {"error": str(exc)}
    return {
        "repository": graph.name,
        "root_path": graph.root_path,
        "files": len(graph.files),
        "symbols": len(graph.symbols),
        "imports": len(graph.imports),
        "overview": overview,
        "summaries": summary_status,
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
def graph(
    limit: int = Query(default=GRAPH_DEFAULT_NODE_LIMIT, ge=1, le=GRAPH_MAX_NODE_LIMIT),
    edge_limit: int = Query(default=GRAPH_DEFAULT_EDGE_LIMIT, ge=1, le=GRAPH_MAX_EDGE_LIMIT),
    repo_path: str | None = None,
) -> dict:
    with neo4j_store() as store:
        return store.graph_slice(limit=limit, edge_limit=edge_limit, repo_path=repo_path)


@router.post("/query")
async def query(request: QueryRequest) -> dict:
    with neo4j_store() as store:
        return await answer_architecture_question(store, request.question, request.repo_path)


@router.post("/impact")
async def impact(request: ImpactRequest) -> dict:
    with neo4j_store() as store:
        return await explain_impact(store, request.path, request.depth, request.repo_path)


@router.get("/file-detail")
def file_detail(path: str, repo_path: str | None = None) -> dict:
    with neo4j_store() as store:
        detail = store.file_detail(path, repo_path=repo_path)
        if not detail:
            raise HTTPException(status_code=404, detail="File not found in graph")
        return detail


@router.post("/summaries")
async def summaries(request: SummaryRequest) -> dict:
    with neo4j_store() as store:
        status = await generate_summaries_for_repo(
            store, request.repo_path, max_files=request.max_files
        )
    return {"status": status}
