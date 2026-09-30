import pytest
from unittest.mock import AsyncMock, patch, MagicMock, call

class MockResult:
    def __init__(self, data):
        self._data = data
    def data(self):
        return self._data
    def single(self):
        return self._data[0] if self._data else None
    def __iter__(self):
        return iter(self._data)


@pytest.fixture
def store():
    with patch("app.services.neo4j_store.GraphDatabase") as mock_gdb:
        from app.services.neo4j_store import Neo4jStore
        s = Neo4jStore()
        # Ensure driver is properly mocked
        s.driver = MagicMock()
        return s

from app.models.graph import CodeFile, CodeSymbol, ImportEdge, RepositoryGraph
from app.services.neo4j_store import (
    _search_words,
    GRAPH_MAX_EDGE_LIMIT,
    GRAPH_MAX_NODE_LIMIT,
    WRITE_BATCH_SIZE,
    Neo4jStore,
    _batched,
    clamp_graph_limits,
)


class RecordingTx:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def run(self, cypher: str, **params):
        self.calls.append((cypher, params))
        return None


def _sample_graph() -> RepositoryGraph:
    return RepositoryGraph(
        root_path="/repo/demo",
        name="demo",
        files=[
            CodeFile(path="src/a.ts", language="typescript", loc=20, complexity=2),
            CodeFile(path="src/b.ts", language="typescript", loc=10, complexity=1),
        ],
        symbols=[
            CodeSymbol(
                id="src/a.ts:run:1",
                file_path="src/a.ts",
                name="run",
                kind="function",
                signature="function run()",
                start_line=1,
                end_line=4,
            )
        ],
        imports=[
            ImportEdge(
                source_path="src/a.ts",
                target="./b",
                target_path="src/b.ts",
                line_number=1,
            ),
            ImportEdge(source_path="src/a.ts", target="react", line_number=2),
        ],
    )


def test_clamp_graph_limits_caps_and_floors() -> None:
    assert clamp_graph_limits(9999, 9999) == (GRAPH_MAX_NODE_LIMIT, GRAPH_MAX_EDGE_LIMIT)
    assert clamp_graph_limits(0, 0) == (1, 1)
    assert clamp_graph_limits(80, 200) == (80, 200)


def test_batched_splits_rows() -> None:
    rows = list(range(WRITE_BATCH_SIZE + 3))
    batches = list(_batched(rows))
    assert len(batches) == 2
    assert len(batches[0]) == WRITE_BATCH_SIZE
    assert batches[1] == [WRITE_BATCH_SIZE, WRITE_BATCH_SIZE + 1, WRITE_BATCH_SIZE + 2]


def test_write_graph_uses_unwind_batches_and_stale_file_cleanup() -> None:
    tx = RecordingTx()
    Neo4jStore._write_graph(tx, _sample_graph())
    statements = [cypher for cypher, _params in tx.calls]
    params = [payload for _cypher, payload in tx.calls]

    assert any("UNWIND $files AS file" in statement for statement in statements)
    assert any("UNWIND $symbols AS symbol" in statement for statement in statements)
    assert any("UNWIND $imports AS edge" in statement for statement in statements)
    assert any("UNWIND $deps AS edge" in statement for statement in statements)
    assert any("WHERE NOT f.key IN $keys" in statement for statement in statements)
    assert any("WHERE NOT ()-[:DEPENDS_ON]->(dep)" in statement for statement in statements)

    file_batch = next(payload["files"] for payload in params if "files" in payload)
    assert {row["key"] for row in file_batch} == {"/repo/demo:src/a.ts", "/repo/demo:src/b.ts"}
    assert {"size_bytes", "mtime_ns", "content_hash"} <= set(file_batch[0]["props"])
    symbol_batch = next(payload["symbols"] for payload in params if "symbols" in payload)
    assert symbol_batch[0]["id"] == "/repo/demo:src/a.ts:run:1"
    assert symbol_batch[0]["props"]["local_id"] == "src/a.ts:run:1"
    import_batch = next(payload["imports"] for payload in params if "imports" in payload)
    assert import_batch[0]["target_key"] == "/repo/demo:src/b.ts"
    dep_batch = next(payload["deps"] for payload in params if "deps" in payload)
    assert dep_batch[0]["target"] == "react"


def test_neo4j_semantic_search(store):
    mock_session = store.driver.session.return_value.__enter__.return_value
    mock_session.run.return_value = MockResult([{"path": "a.py", "score": 0.9, "summary": "test summary"}])
    
    results = store.semantic_search([0.1, 0.2, 0.3], limit=1, repo_path="repo1")
    
    assert len(results) == 1
    assert results[0]["path"] == "a.py"


def test_neo4j_search_files(store):
    mock_session = store.driver.session.return_value.__enter__.return_value
    mock_session.run.return_value = MockResult([{
        "path": "b.py",
        "language": "python",
        "symbols": ["b_func"],
        "imports": ["sys"],
        "dependents": [],
        "external_deps": [],
        "load_bearing_score": 10.0
    }])
    
    results = store.search_files("b_func", limit=1, repo_path="repo1")
    
    assert len(results) == 1
    assert results[0]["path"] == "b.py"


def test_neo4j_impact_for_file(store):
    mock_session = store.driver.session.return_value.__enter__.return_value
    mock_session.run.side_effect = [
        MockResult([{"direct_dependents": ["c.py"]}]),
        MockResult([{"path": "d.py", "distance": 2}])
    ]
    
    impact = store.impact_for_file("a.py", depth=2, repo_path="repo1")
    
    assert impact["target"] == "a.py"
    assert impact["direct_dependents"] == ["c.py"]
    assert len(impact["transitive_dependents"]) == 1
    assert impact["transitive_dependents"][0]["path"] == "d.py"


def test_neo4j_upsert_file_summary(store):
    mock_session = store.driver.session.return_value.__enter__.return_value
    
    store.upsert_file_summary(
        repo_path="repo1",
        file_path="a.py",
        summary_text="test summary",
        embedding=[0.1, 0.2],
        model="test-model",
        provider="test-provider"
    )
    
    args, kwargs = mock_session.run.call_args
    assert "MERGE (s:Summary" in args[0]
    assert kwargs["text"] == "test summary"


def test_neo4j_top_load_bearing_files(store):
    mock_session = store.driver.session.return_value.__enter__.return_value
    mock_session.run.return_value = MockResult([{
        "path": "a.py",
        "language": "python",
        "load_bearing_score": 15.0
    }])
    
    results = store.top_load_bearing_files(limit=1)
    
    assert len(results) == 1
    assert results[0]["path"] == "a.py"


def test_neo4j_file_detail_and_paths(store):
    mock_session = store.driver.session.return_value.__enter__.return_value
    
    def mock_run_side_effect(*args, **kwargs):
        query = args[0]
        if "max_c" in query and "max_fi" in query and "RETURN coalesce" in query:
            return MockResult([{"max_c": 1, "max_ch": 1, "max_fi": 1}])
        if "r.indexed_at DESC" in query:
            return MockResult([{
                "path": "a.py",
                "language": "python",
                "loc": 10,
                "complexity": 1,
                "churn_count": 0,
                "last_modified": None,
                "load_bearing_score": 10,
                "architectural_role": None,
                "is_test_file": False,
                "test_category": None,
                "framework": None,
                "architecture_layer": None,
                "semantic_risk_score": 0,
                "risk_category": None,
                "is_dead_code": False,
                "dead_code_category": None,
                "needs_summary": False,
                "symbols": [],
                "imports": [],
                "dependents": [],
                "external_deps": [],
                "summary": "test",
                "risk_components": {}
            }])
        if "f.language AS language" in query:
            return MockResult([{"path": "a.py", "language": "python", "loc": 10}])
        if "ORDER BY path ASC" in query or "ORDER BY f.path" in query or "RETURN f.path AS path" in query:
            return MockResult([{"path": "a.py"}, {"path": "b.py"}])
        return MockResult([{"path": "a.py", "language": "python", "loc": 10}])
    
    mock_session.run.side_effect = mock_run_side_effect
    
    # Test file_detail
    detail = store.file_detail("a.py", "repo1")
    assert detail["path"] == "a.py"
    
    # Test file_paths
    paths = store.file_paths("repo1")
    assert paths == ["a.py", "b.py"]
    
    # Test files_list
    files = store.files_list("repo1")
    assert files[0]["language"] == "python"


def test_neo4j_get_existing_summary(store):
    mock_session = store.driver.session.return_value.__enter__.return_value
    mock_session.run.return_value = MockResult([{"text": "old summary", "model": "old-model", "provider": "old-provider", "file_path": "a.py", "updated_at": "now"}])
    
    summary = store.get_existing_summary("repo1", "a.py")
    
    assert summary["text"] == "old summary"



@pytest.fixture(autouse=True)
def mock_jev_responses(monkeypatch):
    from app.services.jev_client import jev_client, JevResult, JevDecision
    
    async def dummy_assess(*args, **kwargs):
        return JevResult({
            "cohesion": JevDecision({"score": 5}),
            "coupling": JevDecision({"score": 2}),
            "extraction_readiness": JevDecision({"choice": "easy"})
        })

    monkeypatch.setattr(jev_client, "assess_cluster", dummy_assess)


def test_ensure_schema():
    with patch("app.services.neo4j_store.GraphDatabase.driver") as mock_driver:
        store = Neo4jStore()
        mock_session = MagicMock()
        store.driver.session.return_value.__enter__.return_value = mock_session
        store.ensure_schema()
        assert mock_session.run.call_count == 9


def test_ensure_schema_invalid_dim():
    with patch("app.core.config.settings.embedding_dimensions", 0):
        with patch("app.services.neo4j_store.GraphDatabase.driver") as mock_driver:
            store = Neo4jStore()
            with pytest.raises(ValueError):
                store.ensure_schema()


def test_upsert_repository_graph():
    with patch("app.services.neo4j_store.GraphDatabase.driver") as mock_driver:
        store = Neo4jStore()
        mock_session = MagicMock()
        store.driver.session.return_value.__enter__.return_value = mock_session
        store.ensure_schema = MagicMock()
        graph = RepositoryGraph(name="test", root_path="/test", files=[], internal_edges=[], external_edges=[])
        graph = RepositoryGraph(name="test", root_path="/test", files=[], internal_edges=[], external_edges=[])
        store.upsert_repository_graph(graph)
        store.ensure_schema.assert_called_once()
        mock_session.execute_write.assert_called_once()


def test_scan_cache():
    with patch("app.services.neo4j_store.GraphDatabase.driver") as mock_driver:
        store = Neo4jStore()
        mock_session = MagicMock()
        store.driver.session.return_value.__enter__.return_value = mock_session
        
        # Mock file, symbol, internal_imports, external_imports
        mock_session.run.side_effect = [
            [{"path": "a.py", "language": "python", "loc": 10, "complexity": 5, "load_bearing_score": 2}],
            [{"file_path": "a.py", "id": "foo", "name": "foo", "kind": "func", "start_line": 1, "end_line": 5}],
            [{"source_path": "a.py", "target": "b", "target_path": "b.py", "line_number": 1}],
            [{"source_path": "a.py", "target": "req", "target_path": None, "line_number": None}]
        ]
        
        cache = store.scan_cache("/test")
        assert "a.py" in cache
        assert len(cache["a.py"].symbols) == 1
        assert len(cache["a.py"].imports) == 2


def test_semantic_search_empty():
    with patch("app.services.neo4j_store.GraphDatabase.driver"):
        store = Neo4jStore()
        assert store.semantic_search([]) == []


def test_search_files_empty():
    with patch("app.services.neo4j_store.GraphDatabase.driver"):
        store = Neo4jStore()
        assert store.search_files("") == []


def test_file_detail_not_found():
    with patch("app.services.neo4j_store.GraphDatabase.driver") as mock_driver:
        store = Neo4jStore()
        mock_session = MagicMock()
        store.driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value.single.return_value = None
        assert store.file_detail("missing.py") == {}


@pytest.mark.asyncio
async def test_neo4j_graph_slice(store):
    session = store.driver.session.return_value.__enter__.return_value
    def mock_run(query, **kwargs):
        if "cluster AS name" in query:
            return MockResult([{"name": "a", "internal_edges": 1, "external_in": 1, "external_out": 1}])
        if "f.key AS id" in query:
            return MockResult([{"id": "a.py", "group": "File", "label": "a.py", "props": {}}])
        if "id(source) AS source" in query:
            return MockResult([{"source": "a.py", "target": "b.py", "type": "IMPORTS"}])
        return MockResult([{"total": 1, "name": "a", "id": "a.py", "internal_edges": 1, "external_in": 1, "external_out": 1, "files": 1, "avg_score": 1, "max_score": 1}])
    session.run.side_effect = mock_run
    res = await store.graph_slice(repo_path="/repo")
    assert isinstance(res, dict)


def test_neo4j_store_methods(store):
    # overview
    session = store.driver.session.return_value.__enter__.return_value
    session.run.return_value = MockResult([{"file_count": 1, "loc": 10}])
    res = store.overview(repo_path="/repo")
    assert res["file_count"] == 1
    
    # repositories
    session.run.return_value = MockResult([{"r": {"root_path": "/repo"}}])
    assert len(store.repositories()) == 1


def test_neo4j_clusters(store):
    session = store.driver.session.return_value.__enter__.return_value
    session.run.return_value = [{"name": "a", "source_module": "a", "target_module": "b", "weight": 1}]
    res = store.cluster_edge_counts(session, "/repo")
    assert len(res) == 1


def test_scan_cache(store):
    session = store.driver.session.return_value.__enter__.return_value
    def mock_run(query, **kwargs):
        if "f.path AS path" in query:
            return [{"path": "a.py", "language": "python", "loc": 10}]
        if "s.id AS id" in query:
            return [{"id": "sym", "file_path": "a.py", "name": "a", "kind": "func", "start_line": 1, "end_line": 2, "complexity": 1}]
        if "i.source_path" in query:
            return [{"source_path": "a.py", "target": "b", "target_path": None, "line_number": None}]
        return []
    session.run.side_effect = mock_run
    cache = store.scan_cache("/repo")
    assert "a.py" in cache


def test_clamp_graph_limits():
    n, l = clamp_graph_limits(1, 2)
    assert n == 1


def test_search_words():
    assert "test" in _search_words("Test")
