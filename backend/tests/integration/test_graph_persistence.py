from pathlib import Path

import pytest

from app.indexing.scanner import scan_repository


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scan_write_read_and_rescan_removes_stale_graph_data(
    neo4j_store, sample_repository: Path
) -> None:
    neo4j_store.upsert_repository_graph(await scan_repository(str(sample_repository)))

    assert [item["path"] for item in neo4j_store.files_list(str(sample_repository))] == [
        "main.py",
        "service.py",
    ]
    graph = await neo4j_store.graph_slice(repo_path=str(sample_repository))
    assert {(edge["source"].split(":")[-1], edge["target"].split(":")[-1]) for edge in graph["edges"]} == {
        ("main.py", "service.py")
    }

    (sample_repository / "service.py").unlink()
    neo4j_store.upsert_repository_graph(await scan_repository(str(sample_repository)))

    assert [item["path"] for item in neo4j_store.files_list(str(sample_repository))] == ["main.py"]
    assert (await neo4j_store.graph_slice(repo_path=str(sample_repository)))["edges"] == []
