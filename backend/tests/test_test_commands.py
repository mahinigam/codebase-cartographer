from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INTEGRATION_COMPOSE = REPO_ROOT / "docker-compose.integration.yml"
INTEGRATION_SCRIPT = REPO_ROOT / "scripts" / "test-integration.sh"
E2E_SCRIPT = REPO_ROOT / "scripts" / "test-e2e.sh"
CHECK_SCRIPT = REPO_ROOT / "check.sh"
GITIGNORE = REPO_ROOT / ".gitignore"
README = REPO_ROOT / "README.md"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


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


def test_default_gate_runs_rust_unit_tests() -> None:
    assert "cargo test --manifest-path rust/Cargo.toml" in CHECK_SCRIPT.read_text()


def test_ci_installs_pinned_rust_before_backend_sync() -> None:
    contents = CI_WORKFLOW.read_text()
    assert "dtolnay/rust-toolchain@1.94.0" in contents
    assert contents.index("dtolnay/rust-toolchain@1.94.0") < contents.index("uv sync")


def test_parallel_coverage_files_are_ignored() -> None:
    assert ".coverage.*" in GITIGNORE.read_text()


def test_readme_documents_test_tiers() -> None:
    readme = README.read_text().lower()
    for command in ("./check.sh", "./scripts/test-integration.sh", "./scripts/test-e2e.sh"):
        assert command in readme
    assert "opt-in" in readme
