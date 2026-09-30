from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from app.main import app

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import routes
from app.core.config import settings


def test_api_token_is_optional_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_token", None)

    routes.require_api_token(None, None)


def test_api_token_rejects_missing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_token", "secret")

    with pytest.raises(HTTPException) as exc:
        routes.require_api_token(None, None)

    assert exc.value.status_code == 401


def test_api_token_accepts_bearer_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_token", "secret")

    routes.require_api_token("Bearer secret", None)


def test_scan_rate_limit_rejects_excess_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "scan_rate_limit_per_minute", 1)
    routes._rate_windows.clear()
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))

    routes._enforce_rate_limit(request)
    with pytest.raises(HTTPException) as exc:
        routes._enforce_rate_limit(request)

    assert exc.value.status_code == 429



client = TestClient(app)

@pytest.fixture
def mock_store_fixture():
    with patch("app.api.routes.neo4j_store") as mock_neo4j_store:
        mock_instance = MagicMock()
        mock_instance.graph_slice = AsyncMock()
        mock_neo4j_store.return_value.__enter__.return_value = mock_instance
        yield mock_instance

def test_health(mock_store_fixture):
    mock_store_fixture.ping.return_value = True
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"ok": True, "neo4j": True}

    mock_store_fixture.ping.side_effect = Exception("db down")
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"ok": True, "neo4j": False}

def test_get_overview(mock_store_fixture):
    mock_store_fixture.overview.return_value = {"file_count": 5}
    mock_store_fixture.top_load_bearing_files.return_value = []
    response = client.get("/api/overview")
    assert response.status_code == 200
    assert response.json() == {"overview": {"file_count": 5}, "load_bearing": []}

    response = client.get("/api/overview?repo_path=/test")
    assert response.status_code == 200
    mock_store_fixture.overview.assert_called_with(repo_path="/test")

def test_get_repositories(mock_store_fixture):
    mock_store_fixture.repositories.return_value = ["/repo1", "/repo2"]
    response = client.get("/api/repositories")
    assert response.status_code == 200
    assert response.json() == {"repositories": ["/repo1", "/repo2"]}

def test_get_files(mock_store_fixture):
    mock_store_fixture.files_list.return_value = [{"path": "a.py"}]
    response = client.get("/api/files")
    assert response.status_code == 200
    assert response.json() == {"files": [{"path": "a.py"}]}
    
    response = client.get("/api/files?repo_path=/repo")
    assert response.status_code == 200
    mock_store_fixture.files_list.assert_called_with(repo_path="/repo")

def test_get_graph(mock_store_fixture):
    mock_store_fixture.graph_slice.return_value = {"nodes": [], "edges": []}
    response = client.get("/api/graph")
    assert response.status_code == 200
    assert response.json() == {"nodes": [], "edges": []}

    response = client.get("/api/graph?repo_path=/repo&limit=5&edge_limit=10")
    assert response.status_code == 200
    mock_store_fixture.graph_slice.assert_called_with(limit=5, edge_limit=10, repo_path="/repo", path_prefix=None)

def test_search(mock_store_fixture):
    mock_store_fixture.search_files.return_value = [{"path": "a.py", "score": 1.0}]
    response = client.get("/api/search?q=test")
    assert response.status_code == 200
    assert response.json() == {"results": [{"path": "a.py", "score": 1.0}]}

    response = client.get("/api/search?q=test&repo_path=/repo")
    assert response.status_code == 200
    mock_store_fixture.search_files.assert_called_with("test", limit=8, repo_path="/repo")

@patch("app.api.routes.answer_architecture_question", new_callable=AsyncMock)
def test_query(mock_answer, mock_store_fixture):
    mock_answer.return_value = {"answer": "Some answer", "relevant_files": ["a.py"]}
    response = client.post("/api/query", json={"question": "how does it work?"})
    assert response.status_code == 200
    assert response.json() == {"answer": "Some answer", "relevant_files": ["a.py"]}

@patch("app.api.routes.explain_impact", new_callable=AsyncMock)
def test_impact(mock_explain, mock_store_fixture):
    mock_explain.return_value = {"explanation": "Some explanation"}
    response = client.post("/api/impact", json={"path": "a.py"})
    assert response.status_code == 200
    assert response.json() == {"explanation": "Some explanation"}

def test_get_file_detail(mock_store_fixture):
    mock_store_fixture.file_detail.return_value = {"path": "a.py"}
    response = client.get("/api/file-detail?path=a.py")
    assert response.status_code == 200
    assert response.json() == {"path": "a.py"}

    mock_store_fixture.file_detail.return_value = None
    response = client.get("/api/file-detail?path=missing.py")
    assert response.status_code == 404

@patch("app.api.routes.generate_summaries_for_repo", new_callable=AsyncMock)
def test_summaries(mock_gen, mock_store_fixture):
    mock_gen.return_value = {"requested": 1, "completed": 1, "failed": 0}
    response = client.post("/api/summaries", json={"repo_path": "/repo"})
    assert response.status_code == 200
    assert response.json() == {"status": {"requested": 1, "completed": 1, "failed": 0}}

@patch("app.api.routes.validate_repo_path")
@patch("app.api.routes.scan_repository", new_callable=AsyncMock)
def test_scan(mock_scan, mock_validate, mock_store_fixture):
    mock_validate.return_value = "/repo"
    
    mock_graph = MagicMock()
    mock_graph.name = "test_repo"
    mock_graph.root_path = "/repo"
    mock_graph.files = [1, 2]
    mock_graph.symbols = [1, 2, 3]
    mock_graph.imports = [1]
    mock_scan.return_value = mock_graph
    
    mock_store_fixture.overview.return_value = {"file_count": 2}
    
    response = client.post("/api/scan", json={"path": "/repo", "summarize": False, "incremental": False})
    assert response.status_code == 200
    assert response.json() == {
        "repository": "test_repo",
        "root_path": "/repo",
        "files": 2,
        "symbols": 3,
        "imports": 1,
        "overview": {"file_count": 2},
        "summaries": None
    }

@pytest.mark.asyncio
async def test_scan_unsafe_repo_path(monkeypatch):
    from starlette.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    from app.indexing.scanner import UnsafeRepositoryPath
    def mock_validate(*a):
        raise UnsafeRepositoryPath("unsafe")
    monkeypatch.setattr("app.api.routes.validate_repo_path", mock_validate)
    resp = client.post("/api/scan", json={"path": "../unsafe"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "unsafe"

@pytest.mark.asyncio
async def test_scan_unsafe_repo_from_scan(monkeypatch, mock_store_fixture):
    from starlette.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    from app.indexing.scanner import UnsafeRepositoryPath
    monkeypatch.setattr("app.api.routes.validate_repo_path", lambda x: "/repo")
    async def mock_scan(*a, **k):
        raise UnsafeRepositoryPath("unsafe from scan")
    monkeypatch.setattr("app.api.routes.scan_repository", mock_scan)
    resp = client.post("/api/scan", json={"path": "/repo"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "unsafe from scan"

@pytest.mark.asyncio
async def test_scan_summary_exception(monkeypatch, mock_store_fixture):
    from starlette.testclient import TestClient
    from app.main import app
    from unittest.mock import MagicMock
    client = TestClient(app)
    monkeypatch.setattr("app.api.routes.validate_repo_path", lambda x: "/repo")
    mock_graph = MagicMock()
    mock_graph.name = "repo"
    mock_graph.root_path = "/repo"
    mock_graph.files = []
    mock_graph.symbols = []
    mock_graph.imports = []
    async def mock_scan(*a, **k):
        return mock_graph
    monkeypatch.setattr("app.api.routes.scan_repository", mock_scan)
    async def mock_gen_sum(*a, **k):
        raise Exception("gen fail")
    monkeypatch.setattr("app.api.routes.generate_summaries_for_repo", mock_gen_sum)
    resp = client.post("/api/scan", json={"path": "/repo", "summarize": True})
    assert resp.status_code == 200
    assert resp.json()["summaries"] == {"error": "gen fail"}
