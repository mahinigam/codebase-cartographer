import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INTEGRATION_COMPOSE = REPO_ROOT / "docker-compose.integration.yml"
INTEGRATION_SCRIPT = REPO_ROOT / "scripts" / "test-integration.sh"
E2E_SCRIPT = REPO_ROOT / "scripts" / "test-e2e.sh"
LIVE_PROVIDER_SMOKE_SCRIPT = REPO_ROOT / "scripts" / "test-live-provider-smoke.sh"
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


def test_integration_script_preserves_test_and_cleanup_failures() -> None:
    contents = INTEGRATION_SCRIPT.read_text()
    assert "local status=$?" in contents
    assert "trap - EXIT" in contents
    assert "down --volumes --remove-orphans" in contents


@pytest.mark.parametrize(
    ("up_status", "test_status", "down_status", "expected_status"),
    [(0, 23, 42, 23), (0, 0, 42, 42), (37, 0, 42, 37)],
)
def test_integration_script_returns_the_original_or_cleanup_status(
    tmp_path: Path,
    up_status: int,
    test_status: int,
    down_status: int,
    expected_status: int,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
case " $* " in
  *" up --wait neo4j "*) exit "$FAKE_COMPOSE_UP_STATUS" ;;
  *" down --volumes --remove-orphans "*) exit "$FAKE_COMPOSE_DOWN_STATUS" ;;
esac
exit 0
"""
    )
    uv = bin_dir / "uv"
    uv.write_text('#!/bin/sh\nexit "$FAKE_TEST_STATUS"\n')
    docker.chmod(0o755)
    uv.chmod(0o755)

    env = os.environ | {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "FAKE_COMPOSE_UP_STATUS": str(up_status),
        "FAKE_COMPOSE_DOWN_STATUS": str(down_status),
        "FAKE_TEST_STATUS": str(test_status),
    }
    bash = shutil.which("bash")
    assert bash is not None
    # The script path is fixed; only the fake tools in PATH are test-controlled.
    result = subprocess.run(  # noqa: S603
        [bash, str(INTEGRATION_SCRIPT)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == expected_status
    if down_status != 0:
        assert "Compose cleanup failed with status 42." in result.stderr


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


def test_ci_runs_integration_in_a_separate_credential_free_job() -> None:
    contents = CI_WORKFLOW.read_text()
    match = re.search(
        r"(?ms)^  integration:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
        contents,
    )
    assert match is not None
    integration_job = match.group(1)
    assert "run: ./scripts/test-integration.sh" in integration_job
    assert "secrets." not in integration_job


def test_e2e_launcher_owns_its_server_and_private_log() -> None:
    contents = E2E_SCRIPT.read_text()
    assert "cartographer-e2e-server.pid" not in contents
    assert 'server_log="$(mktemp "${TMPDIR:-/tmp}/cartographer-e2e.' in contents
    assert "Port 5183 is already serving a response" in contents
    assert "trap cleanup EXIT" in contents
    assert 'kill "$server_pid"' in contents
    assert 'wait "$server_pid"' in contents
    assert 'cat "$server_log" >&2' in contents
    assert 'rm -f -- "$server_log"' in contents
    assert "NEXT_TELEMETRY_DISABLED=1" in contents


def test_ci_runs_browser_e2e_in_a_separate_credential_free_job() -> None:
    contents = CI_WORKFLOW.read_text()
    match = re.search(
        r"(?ms)^  e2e:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
        contents,
    )
    assert match is not None
    e2e_job = match.group(1)
    assert 'node-version: "22"' in e2e_job
    assert "playwright install --with-deps chromium" in e2e_job
    assert "run: ./scripts/test-e2e.sh" in e2e_job
    assert "secrets." not in e2e_job


def test_parallel_coverage_files_are_ignored() -> None:
    assert ".coverage.*" in GITIGNORE.read_text()


def test_readme_documents_test_tiers() -> None:
    readme = README.read_text().lower()
    for command in (
        "bash ./check.sh",
        "./scripts/test-integration.sh",
        "./scripts/test-e2e.sh",
        "uv run playwright install chromium",
        "./scripts/test-live-provider-smoke.sh",
    ):
        assert command in readme
    assert "opt-in" in readme
    assert "providers are mocked" in readme
    assert "three independent jobs" in readme
    for job in ("`check`", "`integration`", "`e2e`"):
        assert job in readme
    assert "never runs in ci" in readme


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({}, "Set RUN_LIVE_PROVIDER_SMOKE=1"),
        (
            {
                "RUN_LIVE_PROVIDER_SMOKE": "1",
                "LLM_PROVIDER": "gemini",
                "GEMINI_API_KEY": "",
            },
            "GEMINI_API_KEY is required.",
        ),
        (
            {
                "RUN_LIVE_PROVIDER_SMOKE": "1",
                "LLM_PROVIDER": "ollama",
                "OLLAMA_BASE_URL": "",
            },
            "OLLAMA_BASE_URL is required.",
        ),
        (
            {"RUN_LIVE_PROVIDER_SMOKE": "1", "LLM_PROVIDER": "other"},
            "LLM_PROVIDER must be gemini or ollama.",
        ),
    ],
)
def test_live_provider_smoke_rejects_unapproved_or_unconfigured_calls(
    tmp_path: Path, overrides: dict[str, str], message: str
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv_marker = tmp_path / "uv-was-called"
    uv = bin_dir / "uv"
    uv.write_text('#!/bin/sh\n: > "$PROVIDER_UV_MARKER"\nexit 91\n')
    uv.chmod(0o755)
    env = os.environ.copy()
    for key in (
        "RUN_LIVE_PROVIDER_SMOKE",
        "LLM_PROVIDER",
        "GEMINI_API_KEY",
        "OLLAMA_BASE_URL",
    ):
        env.pop(key, None)
    env.update(overrides)
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "PROVIDER_UV_MARKER": str(uv_marker),
        }
    )
    bash = shutil.which("bash")
    assert bash is not None
    result = subprocess.run(  # noqa: S603
        [bash, str(LIVE_PROVIDER_SMOKE_SCRIPT)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 2
    assert message in result.stderr
    assert not uv_marker.exists()


def _fake_provider_environment(
    tmp_path: Path, provider: str, response: str
) -> tuple[dict[str, str], Path]:
    module_root = tmp_path / "fake-modules"
    package_dirs = (
        module_root / "app",
        module_root / "app" / "core",
        module_root / "app" / "services",
    )
    for package_dir in package_dirs:
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").write_text("")

    (module_root / "app" / "core" / "config.py").write_text(
        """import os

class Settings:
    llm_provider = os.environ["LLM_PROVIDER"]

settings = Settings()
"""
    )
    (module_root / "app" / "services" / "llm.py").write_text(
        """import os

class LLMClient:
    async def _record(self, provider, prompt):
        with open(os.environ["PROVIDER_CALL_LOG"], "a") as calls:
            calls.write(provider + "\\n")
        return os.environ["SMOKE_RESPONSE"]

    async def _gemini(self, prompt):
        return await self._record("gemini", prompt)

    async def _ollama(self, prompt):
        return await self._record("ollama", prompt)
"""
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    python_code = (
        "import os, sys; "
        'sys.path.insert(0, os.environ["FAKE_PROVIDER_MODULES"]); '
        "exec(sys.stdin.read())"
    )
    uv.write_text(f"#!/bin/sh\nexec {shlex.quote(sys.executable)} -c {shlex.quote(python_code)}\n")
    uv.chmod(0o755)

    call_log = tmp_path / "provider-calls.log"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "RUN_LIVE_PROVIDER_SMOKE": "1",
            "LLM_PROVIDER": provider,
            "GEMINI_API_KEY": "test-key" if provider == "gemini" else "",
            "OLLAMA_BASE_URL": ("http://127.0.0.1:11434" if provider == "ollama" else ""),
            "FAKE_PROVIDER_MODULES": str(module_root),
            "PROVIDER_CALL_LOG": str(call_log),
            "SMOKE_RESPONSE": response,
        }
    )
    return env, call_log


def _run_live_provider_smoke(
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    assert bash is not None
    return subprocess.run(  # noqa: S603
        [bash, str(LIVE_PROVIDER_SMOKE_SCRIPT)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )


@pytest.mark.parametrize("provider", ["gemini", "ollama"])
def test_live_provider_smoke_makes_one_direct_call(tmp_path: Path, provider: str) -> None:
    env, call_log = _fake_provider_environment(tmp_path, provider, "READY")
    result = _run_live_provider_smoke(env)
    contents = LIVE_PROVIDER_SMOKE_SCRIPT.read_text()

    assert result.returncode == 0, result.stderr
    assert "response omitted" in result.stdout
    assert call_log.read_text().splitlines() == [provider]
    assert "timeout=45" in contents
    assert "client.complete(" not in contents


def test_live_provider_smoke_rejects_an_empty_provider_response(
    tmp_path: Path,
) -> None:
    env, call_log = _fake_provider_environment(tmp_path, "gemini", "")
    result = _run_live_provider_smoke(env)

    assert result.returncode != 0
    assert "did not return a live completion" in result.stderr
    assert call_log.read_text().splitlines() == ["gemini"]


def test_live_provider_smoke_is_not_part_of_automatic_gates() -> None:
    assert LIVE_PROVIDER_SMOKE_SCRIPT.exists()
    assert "test-live-provider-smoke.sh" not in CHECK_SCRIPT.read_text()
    assert "test-live-provider-smoke.sh" not in CI_WORKFLOW.read_text()
