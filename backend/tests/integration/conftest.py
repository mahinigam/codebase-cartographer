import os
from pathlib import Path

import pytest
from neo4j import GraphDatabase

from app.core.config import settings
from app.services.jev_client import jev_client
from app.services.neo4j_store import Neo4jStore


def _neo4j_is_reachable() -> bool:
    driver = None
    try:
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
            connection_timeout=1.5,
        )
        driver.verify_connectivity()
        return True
    except Exception:
        return False
    finally:
        if driver is not None:
            driver.close()


def pytest_collection_modifyitems(config, items) -> None:
    if os.environ.get("CARTOGRAPHER_RUN_INTEGRATION") == "1":
        return
    integration_items = [item for item in items if "integration" in item.keywords]
    if not integration_items or _neo4j_is_reachable():
        return
    marker = pytest.mark.skip(
        reason=(
            f"Neo4j unreachable at {settings.neo4j_uri} "
            "(set CARTOGRAPHER_RUN_INTEGRATION=1 to require)"
        )
    )
    for item in integration_items:
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
