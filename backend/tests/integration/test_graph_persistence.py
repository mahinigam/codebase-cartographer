from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.indexing.scanner import scan_repository
from app.main import app


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
    edges = {
        (edge["source"].split(":")[-1], edge["target"].split(":")[-1]) for edge in graph["edges"]
    }
    assert edges == {("main.py", "service.py")}

    (sample_repository / "service.py").unlink()
    neo4j_store.upsert_repository_graph(await scan_repository(str(sample_repository)))

    assert [item["path"] for item in neo4j_store.files_list(str(sample_repository))] == ["main.py"]
    assert (await neo4j_store.graph_slice(repo_path=str(sample_repository)))["edges"] == []


@pytest.mark.integration
def test_scan_api_persists_public_reads_and_removes_stale_data(
    neo4j_store, sample_repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "api_token", None)
    monkeypatch.setattr(settings, "allowed_repo_roots_raw", "")

    with TestClient(app) as client:
        response = client.post(
            "/api/scan",
            json={
                "path": str(sample_repository),
                "summarize": False,
                "incremental": False,
            },
        )
        assert response.status_code == 200, response.text
        repo_path = response.json()["root_path"]

        files_response = client.get("/api/files", params={"repo_path": repo_path})
        overview_response = client.get("/api/overview", params={"repo_path": repo_path})
        graph_response = client.get("/api/graph", params={"repo_path": repo_path})

        assert {file["path"] for file in files_response.json()["files"]} == {
            "main.py",
            "service.py",
        }
        assert overview_response.json()["overview"]["files"] == 2
        assert {
            (
                edge["source"].split(":")[-1],
                edge["target"].split(":")[-1],
            )
            for edge in graph_response.json()["edges"]
        } == {("main.py", "service.py")}

        (sample_repository / "service.py").unlink()
        rescan_response = client.post(
            "/api/scan",
            json={
                "path": str(sample_repository),
                "summarize": False,
                "incremental": False,
            },
        )
        assert rescan_response.status_code == 200, rescan_response.text

        files_after_rescan = client.get("/api/files", params={"repo_path": repo_path}).json()[
            "files"
        ]
        graph_after_rescan = client.get("/api/graph", params={"repo_path": repo_path}).json()
        assert {file["path"] for file in files_after_rescan} == {"main.py"}
        assert graph_after_rescan["edges"] == []
