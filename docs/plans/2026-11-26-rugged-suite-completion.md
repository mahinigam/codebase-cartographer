# Rugged Test Suite Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the deterministic, Neo4j integration, browser E2E, and explicitly opt-in provider-smoke test layers without changing production behavior unless a test proves a defect.

**Architecture:** Keep `check.sh` service-free while adding Rust unit tests to its default quality gate. Run Neo4j and Playwright coverage as separate GitHub Actions jobs using the existing local scripts; keep all AI calls mocked except a bounded, user-invoked provider smoke command.

**Tech Stack:** Rust/Cargo, Python/Pytest/FastAPI, Neo4j 5, Docker Compose, Next.js/React, Playwright, Vitest, GitHub Actions.

---

## File map

- `check.sh`: add Rust unit tests to the default gate.
- `.github/workflows/ci.yml`: split default, Neo4j, and browser jobs.
- `backend/tests/integration/`: prove scan, persistence, public reads, rescan, and isolation.
- `frontend/e2e/critical_paths.py`: deterministic end-to-end user workflows and failure states.
- `scripts/test-integration.sh`, `scripts/test-e2e.sh`: robust startup, readiness, and cleanup.
- `scripts/test-live-provider-smoke.sh`: explicit, bounded local provider smoke.
- `README.md`: document commands, prerequisites, and which checks CI runs.
- `backend/tests/test_test_commands.py`: lock in test-tier and command safety contracts.

## Tasks

### Task 1: Include Rust unit tests in the default quality gate

**Files:** Modify `check.sh`, `.github/workflows/ci.yml`, and `backend/tests/test_test_commands.py`.

- [x] Add `test_default_gate_runs_rust_unit_tests`, asserting that `CHECK_SCRIPT.read_text()` contains `cargo test --manifest-path rust/Cargo.toml`.
- [x] Run `cd backend && uv run pytest tests/test_test_commands.py::test_default_gate_runs_rust_unit_tests -q`; it must fail because the script does not invoke Cargo yet.
- [x] In `check.sh`, after `cd backend`, add `cargo test --manifest-path rust/Cargo.toml` before pytest. Do not make Rust tests depend on Docker or external providers.
- [x] Add the pinned Rust 1.94.0 toolchain setup to the existing `check` workflow job before `uv sync`, so CI builds the PyO3 extension and runs Cargo with the repository's declared toolchain.

```yaml
- uses: dtolnay/rust-toolchain@1.94.0
```

- [x] Run `cd backend && cargo test --manifest-path rust/Cargo.toml`, then run `bash ./check.sh`; expect Cargo tests and the existing Python, lint, type, frontend, and coverage checks to pass.
- [x] Commit as `test: include Rust unit tests in default gate`.

### Task 2: Exercise persisted graph data through the public API

**Files:** Modify `backend/tests/integration/test_graph_persistence.py`, `scripts/test-integration.sh`, and `backend/tests/test_test_commands.py`; retain `backend/tests/integration/conftest.py` isolation.

- [x] Add an integration case using `fastapi.testclient.TestClient(app)` and the existing `neo4j_store` fixture with the temporary two-file repository. The fixture clears Neo4j and disables Jev; this keeps the API scan isolated and prevents provider calls. POST `/api/scan` with `{"path": str(sample_repository), "summarize": false, "incremental": false}` and assert HTTP 200.
- [x] Read `/api/files`, `/api/overview`, and `/api/graph` with the returned repository root path; assert both file paths and the `main.py` → `service.py` edge are returned from Neo4j.
- [x] Delete `service.py`, scan again, and assert the public file and graph endpoints no longer expose the stale file or edge.
- [x] Keep the fixture assertions tied to public response shapes:

```python
files = client.get("/api/files", params={"repo_path": str(sample_repository)}).json()["files"]
assert {item["path"] for item in files} == {"main.py", "service.py"}
graph = client.get("/api/graph", params={"repo_path": str(sample_repository)}).json()
assert {
    (edge["source"].split(":")[-1], edge["target"].split(":")[-1])
    for edge in graph["edges"]
} == {
    ("main.py", "service.py")
}
```

The public API already satisfies these behaviors, so this is a coverage addition rather than a production behavior change; the new integration case passed on its first run.

- [x] Run `./scripts/test-integration.sh tests/integration/test_graph_persistence.py -v`; the script changes to `backend` before pytest, so this path is relative to that directory. Expect both direct-store and public-API persistence tests to pass, with Docker resources removed afterward.
- [x] Preserve the pytest exit status in the integration script's `EXIT` trap. If test execution succeeds but Compose cleanup fails, return the cleanup failure; if tests fail, report cleanup failure to stderr without masking the original test failure.
- [x] Extend the command-contract test to verify `docker compose down --volumes --remove-orphans` cleanup, including original-test and cleanup exit-status handling. Run `cd backend && uv run pytest tests/test_test_commands.py -q`.
- [x] Commit as `test: verify persisted graph through API`.

### Task 3: Run Neo4j integration in its own CI job

**Files:** Modify `.github/workflows/ci.yml`.

- [x] Add an `integration` job on `ubuntu-latest` with checkout, Python 3.12, Rust 1.94.0, `uv`, and `cd backend && uv sync`; keep credentials out of the job.
- [x] Use these job actions in order; run the existing script from the repository root after installing the backend:

```yaml
integration:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: "3.12"
    - uses: dtolnay/rust-toolchain@1.94.0
    - run: python -m pip install uv && cd backend && uv sync
    - run: ./scripts/test-integration.sh
```

- [x] Run `./scripts/test-integration.sh` from the repository root. The script owns its Compose project, wait-for-health behavior, test environment, and cleanup trap.
- [x] Keep this job separate from `check`; do not add Docker startup to `check.sh`. Let CI display independent quality and integration outcomes.
- [x] Run `git diff --check` and inspect the workflow to confirm both `push` to `main` and `pull_request` triggers cover the new job. On GitHub, expect a separate `integration` check after the branch is pushed.
- [x] Commit as `ci: run Neo4j integration tests separately`.

### Task 4: Expand browser workflow and failure coverage

**Files:** Modify `frontend/e2e/critical_paths.py`; modify app components only if accessible interaction tests expose a defect.

- [x] Refactor the route fixture to return stable repositories, graph nodes/edges, file detail/risk data, and question evidence for successful responses; allow each API path to be fulfilled with a controlled status/error.
- [x] Use API shapes already declared by `frontend/src/lib/api.ts`: graph nodes have `id`, `label`, `score`, and `labels`; file detail includes `path`, `loc`, `load_bearing_score`, `symbols`, `imports`, and `dependents`; query responses include `answer`, `evidence`, and `semantic_matches`.

```python
query_response = {
    "answer": "main.py starts the application.",
    "evidence": [{"path": "main.py"}],
    "semantic_matches": [
        {"path": "main.py", "summary": "Application entry point", "score": 0.9}
    ],
}
```

- [x] Add independent browser cases for: empty initial workspace; scan loading held by an async route barrier; successful scan → graph node/file inspection → risk view → command-palette question and rendered evidence; scan failure and retry; graph/file/query failure feedback and recovery.
- [x] Use an async Playwright route barrier for loading, not a sleep:

```python
scan_started, release_scan = asyncio.Event(), asyncio.Event()

async def hold_scan(route):
    scan_started.set()
    await release_scan.wait()
    await route.fulfill(status=200, json=scan_response)
```

In the scenario, click **Analyze repository**, await `scan_started`, assert the button says **Scanning repository...** and is disabled inside `try`, and set `release_scan` in `finally` before asserting the success toast. A failed assertion must never leave the intercepted request blocked during browser teardown.
- [x] Capture page errors and unexpected request failures per browser context. Deliberately fulfilled error responses must not be counted as transport failures.
- [x] In the API route fixture, whitelist `/api/repositories`, `/api/scan`, `/api/overview`, `/api/graph`, `/api/files`, `/api/file-detail`, `/api/search`, and `/api/query`; record and abort any other API URL. Add one deliberate `route.abort()` scan case and assert the user sees the error toast and can retry successfully.
- [x] Add keyboard-only checks for the repository input, scan action, command-palette trigger/input, and visible focus; check `scrollWidth <= clientWidth` at 390×844, 768×1024, and 1440×900.
- [x] Run `./scripts/test-e2e.sh`; all seven scenarios pass without fixed sleeps, live backend requests, or provider calls.

The browser regression exposed a silent `refresh()` catch that reported scan success after graph loading failed. `CartographerApp` now propagates refresh errors to scan/repository handlers and reports initial loading failures; focused component tests cover these states.

- [x] Commit as `test: cover browser investigation states`.

### Task 5: Run browser E2E in its own CI job and harden its launcher

**Files:** Modify `.github/workflows/ci.yml`, `scripts/test-e2e.sh`, and `backend/tests/test_test_commands.py`.

- [x] Remove the fixed `/tmp/cartographer-e2e-server.pid` file. Start `next start` from `frontend` in the script process, retain `$!` directly, and use an `EXIT` trap that stops and waits for that exact process while preserving the original exit status.
- [x] Use a private log path and preserve the original status in cleanup:

```bash
server_log="$(mktemp "${TMPDIR:-/tmp}/cartographer-e2e.XXXXXX.log")"
server_pid=""
cleanup() {
  local status=$?
  trap - EXIT
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
  if [[ "$status" -ne 0 && -f "$server_log" ]]; then cat "$server_log" >&2; fi
  rm -f -- "$server_log"
  exit "$status"
}
trap cleanup EXIT
```

Set `NEXT_TELEMETRY_DISABLED=1`, build first, then launch `./node_modules/.bin/next start --hostname 127.0.0.1 --port 5183` directly in the background so `$!` is the server process.
- [x] Make readiness failure print the captured server log and fail after the existing bounded retry loop; do not report success unless the final HTTP probe succeeds.
- [x] Add an `e2e` GitHub job with checkout, Python 3.12, Rust 1.94.0, Node 22, backend `uv sync`, `npm ci`, and `uv run playwright install --with-deps chromium`; run `./scripts/test-e2e.sh`.

```yaml
e2e:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: "3.12"
    - uses: actions/setup-node@v4
      with:
        node-version: "22"
        cache: npm
        cache-dependency-path: frontend/package-lock.json
    - uses: dtolnay/rust-toolchain@1.94.0
    - run: python -m pip install uv && cd backend && uv sync
    - run: npm ci
      working-directory: frontend
    - run: cd backend && uv run playwright install --with-deps chromium
    - run: ./scripts/test-e2e.sh
```

- [x] Extend the command-contract test to verify the launcher owns its server process, uses private cleanup, rejects an occupied port, and has no shared PID file; verify E2E CI setup. Run `cd backend && uv run pytest tests/test_test_commands.py -q`.
- [x] Run `git diff --check`; the workflow has three separate jobs (`check`, `integration`, and `e2e`) on both configured triggers.
- [x] Commit as `ci: run browser E2E tests separately`.

### Task 6: Add an explicitly gated provider smoke command

**Files:** Create `scripts/test-live-provider-smoke.sh`; modify `backend/tests/test_test_commands.py`.

- [x] Make the script reject execution unless `RUN_LIVE_PROVIDER_SMOKE=1`, require `LLM_PROVIDER` to be `gemini` or `ollama`, and require `GEMINI_API_KEY` for Gemini. Print an explicit cost/network warning before making a call.

```bash
#!/usr/bin/env bash
set -euo pipefail

if [[ "${RUN_LIVE_PROVIDER_SMOKE:-}" != "1" ]]; then
  echo "Set RUN_LIVE_PROVIDER_SMOKE=1 to allow a real provider request." >&2
  exit 2
fi
case "${LLM_PROVIDER:-}" in
  gemini) [[ -n "${GEMINI_API_KEY:-}" ]] || { echo "GEMINI_API_KEY is required." >&2; exit 2; } ;;
  ollama) [[ -n "${OLLAMA_BASE_URL:-}" ]] || { echo "OLLAMA_BASE_URL is required." >&2; exit 2; } ;;
  *) echo "LLM_PROVIDER must be gemini or ollama." >&2; exit 2 ;;
esac
echo "WARNING: this sends one live request to ${LLM_PROVIDER}; provider usage may incur cost."
```

- [x] Run exactly one provider transport call through the existing `LLMClient` instance: `client._gemini(prompt)` when `settings.llm_provider == "gemini"` or `client._ollama(prompt)` for Ollama. Do not call `complete()`, whose retry/fallback behavior can make additional requests. Enforce a 45-second timeout and fail on an empty response.

```python
import asyncio
import logging

from app.core.config import settings
from app.services.llm import LLMClient


async def smoke() -> None:
    logging.disable(logging.CRITICAL)
    client = LLMClient()
    try:
        result = await asyncio.wait_for(
            (
                client._gemini("Reply with the single word READY.")
                if settings.llm_provider == "gemini"
                else client._ollama("Reply with the single word READY.")
            ),
            timeout=45,
        )
    except Exception as exc:
        raise SystemExit(f"Provider smoke failed ({type(exc).__name__}); details suppressed.") from None
    if not result.strip():
        raise SystemExit("Selected provider did not return a live completion.")
    print(f"{settings.llm_provider} provider responded; response omitted.")


asyncio.run(smoke())
```

Invoke this only after the shell guard succeeds. The existing provider client is reused, no fallback provider is called, and the explicit transport method ensures a single bounded outbound call.
- [x] Add guard tests for missing opt-in/provider configuration, asserting the runner is never invoked; exercise both provider branches with a fake client to prove exactly one transport method call and empty-response failure without network access.
- [x] Run `cd backend && uv run pytest tests/test_test_commands.py -q`; verify `check.sh` and CI do not invoke this script.

The Gemini and Ollama call paths were exercised using a fake `LLMClient`; no live provider call was made.

- [x] Commit as `test: add gated live provider smoke command`.

### Task 7: Document the finished tiers and verify every safe path

**Files:** Modify `README.md`, `backend/tests/test_test_commands.py`, and `docs/plans/2026-11-26-rugged-test-suite.md`.

- [x] Assert that the live-provider script exists, refuses a missing opt-in flag, and is absent from `check.sh`; assert that README documents the three CI jobs and the provider smoke warning/command.
- [x] Update README with each test tier's prerequisites, exact command, behavior covered, and whether it runs in CI. State that live smoke can make a real provider request and is never part of CI.
- [x] Reconcile the original rugged-suite plan checkboxes with what was actually completed; leave unexecuted live smoke clearly marked opt-in and do not claim a hosted job passed before GitHub reports it.
- [x] Run `bash ./check.sh`, `./scripts/test-integration.sh -v`, and `./scripts/test-e2e.sh`. Expect default checks plus Cargo, real Neo4j assertions, and all browser cases to pass; provider smoke remains uncalled.
- [x] Run `git diff --check`, inspect `git status --short`, and verify generated coverage, server logs, and Compose volumes are not tracked or left running.
- [x] Commit as `docs: document rugged suite execution tiers`.

Verification record:

- The first `bash ./check.sh` invocation could not find `cargo` because rustup was not on the shell's `PATH`. Re-running with `PATH="$(brew --prefix rustup)/bin:$HOME/.cargo/bin:$PATH"` passed: 10 Rust tests, 159 backend tests with 92.25% coverage (90% minimum), 49 frontend tests, lint, and type checks.
- The default backend run intentionally skips the two Neo4j cases unless `CARTOGRAPHER_RUN_INTEGRATION=1`; `./scripts/test-integration.sh -v` then passed both cases.
- `./scripts/test-e2e.sh` passed its production build and all seven browser scenarios. Port 5183 was no longer listening afterward, and no integration Compose project remained. The existing main-repository Compose project was left untouched.
- The local suite emitted existing Starlette/AnyIO deprecation and Node localStorage experimental warnings. No live provider request was made. Hosted GitHub Actions run `45879378037` passed all three jobs (`check`, `integration`, and `e2e`).

## Plan self-review

- **Spec coverage:** default Rust/backend/frontend gate is Task 1; isolated Neo4j persistence, API reads, rescan, and cleanup are Tasks 2–3; browser success/failure/accessibility/responsive coverage and CI are Tasks 4–5; safe live smoke is Task 6; documentation and full validation are Task 7.
- **Scope:** production changes remain conditional on a failing behavior test; AI providers stay mocked outside the separately guarded local smoke.
- **Placeholders:** every task names files, commands, expected outcomes, and commit boundaries. No new API types or unowned helpers are assumed.
- **Final review:** run `git diff --check` and the documented test commands; report provider smoke as unrun unless the user explicitly opts in with credentials.
