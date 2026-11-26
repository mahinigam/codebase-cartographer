from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INTEGRATION_COMPOSE = REPO_ROOT / "docker-compose.integration.yml"
INTEGRATION_SCRIPT = REPO_ROOT / "scripts" / "test-integration.sh"
E2E_SCRIPT = REPO_ROOT / "scripts" / "test-e2e.sh"
CHECK_SCRIPT = REPO_ROOT / "check.sh"
GITIGNORE = REPO_ROOT / ".gitignore"


def test_integration_compose_is_loopback_isolated_and_health_checked() -> None:
    assert INTEGRATION_COMPOSE.exists()
    contents = INTEGRATION_COMPOSE.read_text()
    assert '"127.0.0.1:7689:7687"' in contents
    assert "healthcheck:" in contents
    assert "neo4j:" in contents


def test_extended_test_scripts_cleanup_resources() -> None:
    for script in (INTEGRATION_SCRIPT, E2E_SCRIPT):
        assert script.exists()
        contents = script.read_text()
        assert "set -euo pipefail" in contents
        assert "trap cleanup EXIT" in contents


def test_default_gate_stays_credential_and_service_free() -> None:
    contents = CHECK_SCRIPT.read_text().lower()
    assert "docker compose" not in contents
    assert "playwright" not in contents
    assert "typesafe_api_key" not in contents
    assert "google_api_key" not in contents


def test_parallel_coverage_files_are_ignored() -> None:
    assert ".coverage.*" in GITIGNORE.read_text()
