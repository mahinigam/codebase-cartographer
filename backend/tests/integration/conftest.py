import os
from pathlib import Path

import pytest

from app.services.jev_client import jev_client
from app.services.neo4j_store import Neo4jStore


def pytest_collection_modifyitems(config, items) -> None:
    if os.environ.get("CARTOGRAPHER_RUN_INTEGRATION") == "1":
        return
    marker = pytest.mark.skip(reason="set CARTOGRAPHER_RUN_INTEGRATION=1 to run integration tests")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(marker)


@pytest.fixture
def neo4j_store(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(jev_client, "enabled", False)
    store = Neo4jStore()
    with store.driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    try:
        yield store
    finally:
        with store.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        store.close()


@pytest.fixture
def sample_repository(tmp_path: Path) -> Path:
    (tmp_path / "main.py").write_text("from service import run\nrun()\n")
    (tmp_path / "service.py").write_text("def run():\n    return 'ok'\n")
    return tmp_path
