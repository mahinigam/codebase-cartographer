from app.models.graph import CodeFile, CodeSymbol, ImportEdge, RepositoryGraph
from app.services.neo4j_store import (
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
