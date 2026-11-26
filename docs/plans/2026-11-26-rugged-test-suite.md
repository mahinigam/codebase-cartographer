# Rugged Test Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status: superseded.** This was the initial proposal, not the implementation checklist. Its unchecked steps are preserved as historical scope and must not be read as a current progress report. The approved scope and actual task-by-task completion record are in [Rugged Test Suite Completion](./2026-11-26-rugged-suite-completion.md).

## Reconciliation with the completed work

| Area in this draft | Reconciled status |
| --- | --- |
| Test tiers and commands | Reworked in the approved plan. The default gate remains service-free; integration and E2E run in separate CI jobs. The original private-network test-runner proposal was not used. |
| Neo4j persistence | Completed in the approved plan, including public API scan/read/rescan coverage. The older direct-store test remains in place. |
| Additional API/client boundary cases | Not implemented from this draft; its unchecked cases remain proposals, not completed coverage. |
| Additional adversarial native-scanner cases | Not implemented from this draft. Existing native and Python parity coverage was retained; this draft's proposed cases are not claimed as added. |
| Browser workflow | Implemented under the approved plan with seven isolated scenarios, intercepted APIs, failure/recovery, keyboard, and viewport checks. The draft's screenshot proposal was not part of the final scope. |
| Live-provider smoke | The explicitly gated command was implemented and tested with fake clients only. No live provider request was made. |
| Hosted CI result | The `check`, `integration`, and `e2e` jobs all passed for [PR #3](https://github.com/mahinigam/codebase-cartographer/pull/3) (run `45879378037`). |
| Documentation and local verification | See Task 7 and its final command results in the approved completion plan. |

**Goal:** Add deterministic, layered regression tests and repeatable commands that prove Codebase Cartographer can scan repositories, persist trustworthy graph evidence, and support its core investigation workflow under both normal and failure conditions.

**Architecture:** Keep the existing fast unit suite network-free, add a service-backed Neo4j integration layer behind an explicit command, and test the browser workflow through a controlled local API. The default gate remains fast; integration and browser checks are isolated and opt-in so they are reproducible without credentials or persistent data.

**Tech Stack:** Rust/Cargo, Python 3.11+ with FastAPI/Pytest/Playwright, Neo4j 5 Docker Compose, Next.js/React/TypeScript, Vitest, Docker Compose.

---

## File Structure

| Path | Responsibility |
| --- | --- |
| `backend/pyproject.toml` | Define test markers and the Python browser-test dependency. |
| `backend/tests/integration/conftest.py` | Isolate real Neo4j integration data and make the suite opt-in. |
| `backend/tests/integration/test_graph_persistence.py` | Verify native scan → graph write → graph read and rescan behavior. |
| `backend/tests/test_routes.py` | Cover API validation, limits, and error contracts. |
| `backend/rust/src/*` | Add native-core regression tests beside the code they protect. |
| `frontend/src/lib/api.test.ts` | Assert exact client request/error contracts. |
| `frontend/e2e/critical_paths.py` | Exercise the browser workflow against deterministic responses. |
| `docker-compose.integration.yml` | Run a disposable Neo4j instance isolated from developer data. |
| `backend/Dockerfile.integration` | Build a disposable test runner on the same private Compose network as Neo4j. |
| `scripts/test-integration.sh` | Start, test, and tear down the integration environment. |
| `scripts/test-e2e.sh` | Start the frontend, run headless browser tests, and stop it. |
| `check.sh` | Retain the deterministic default gate and expose explicit extended checks. |
| `.gitignore` | Ignore all generated coverage data, including suffixed parallel-run files. |
| `README.md` | Document local and CI test commands, prerequisites, and opt-in live smoke testing. |

### Task 1: Establish explicit test tiers and commands

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `docker-compose.integration.yml`
- Create: `backend/Dockerfile.integration`
- Create: `scripts/test-integration.sh`
- Create: `scripts/test-e2e.sh`
- Modify: `check.sh`
- Modify: `.gitignore`
- Modify: `README.md`

- [ ] **Step 1: Write the command-contract tests**

Create `backend/tests/test_test_commands.py` to assert that the integration compose file has a single unexposed Neo4j service with a healthcheck, both scripts use strict shell mode and cleanup traps, and `check.sh` does not invoke Docker, Playwright, or external providers.

```python
def test_integration_compose_isolated_and_health_checked() -> None:
    assert INTEGRATION_COMPOSE.exists()
    contents = INTEGRATION_COMPOSE.read_text()
    assert "ports:" not in contents
    assert "healthcheck:" in contents

def test_default_gate_stays_service_free() -> None:
    contents = CHECK_SH.read_text()
    assert "docker compose" not in contents
    assert "playwright" not in contents.lower()
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run: `cd backend && uv run pytest tests/test_test_commands.py -v`

Expected: FAIL because the command/compose files and their contracts do not yet exist.

- [ ] **Step 3: Add isolated commands and configuration**

Add the marker declaration and Playwright development dependency to `backend/pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
  "integration: requires the disposable Neo4j integration service",
]

[dependency-groups]
dev = [
  # retain existing entries
  "playwright>=1.51,<2",
]
```

Create `docker-compose.integration.yml` with a Neo4j-only service, no host ports, a `neo4j-test` password supplied only to the test container, and a healthcheck. Create scripts that generate a unique Compose project name, wait for health, run the marked test target, and always execute `docker compose down --volumes --remove-orphans` in `trap cleanup EXIT`. Add `.coverage.*` to `.gitignore` alongside the existing `.coverage` rule. Keep `check.sh` deterministic; add documented sibling commands rather than silently making local checks require Docker or a browser.

- [ ] **Step 4: Re-run the command-contract tests**

Run: `cd backend && uv run pytest tests/test_test_commands.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the test-tier foundation**

```bash
git add .gitignore backend/pyproject.toml backend/tests/test_test_commands.py docker-compose.integration.yml scripts/test-integration.sh scripts/test-e2e.sh check.sh README.md
git commit -m "test: add isolated integration and browser commands"
```

### Task 2: Prove real Neo4j persistence and rescan safety

**Files:**
- Create: `backend/tests/integration/__init__.py`
- Create: `backend/tests/integration/conftest.py`
- Create: `backend/tests/integration/test_graph_persistence.py`
- Modify: `scripts/test-integration.sh`

- [ ] **Step 1: Write the failing persistence test**

Create a temporary repository fixture containing `main.py` that imports `service.py`. In `test_graph_persistence.py`, scan it with `scan_repository`, store the graph through `Neo4jStore`, then assert repositories, files, graph nodes/edges, and file details are readable through the production store methods. Modify the fixture by deleting `service.py`, rescan, and assert its stale file node and import edge are gone.

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_scan_write_read_and_rescan_removes_stale_graph_data(
    neo4j_store: Neo4jStore, sample_repository: Path,
) -> None:
    first_graph = await scan_repository(str(sample_repository))
    neo4j_store.upsert_repository_graph(first_graph)
    assert [item["path"] for item in neo4j_store.files_list(str(sample_repository))] == [
        "main.py", "service.py"
    ]
    assert {(edge["source"], edge["target"]) for edge in (await neo4j_store.graph_slice(
        repo_path=str(sample_repository)
    ))["edges"]} == {("main.py", "service.py")}

    (sample_repository / "service.py").unlink()
    neo4j_store.upsert_repository_graph(await scan_repository(str(sample_repository)))
    assert [item["path"] for item in neo4j_store.files_list(str(sample_repository))] == ["main.py"]
```

- [ ] **Step 2: Run the marked test and verify it fails before the harness exists**

Run: `./scripts/test-integration.sh backend/tests/integration/test_graph_persistence.py -v`

Expected: FAIL because the script, real-store fixture, and service configuration are absent.

- [ ] **Step 3: Add an isolated integration fixture**

In `backend/tests/integration/conftest.py`, require `CARTOGRAPHER_RUN_INTEGRATION=1`; otherwise skip marked tests with a clear message. Read `NEO4J_TEST_URI`, `NEO4J_TEST_USER`, and `NEO4J_TEST_PASSWORD`, clear only the disposable graph before and after each test using the production driver, and yield a production `Neo4jStore`. Build every source fixture beneath `tmp_path`; never scan the checkout or developer paths. Have `scripts/test-integration.sh` pass those variables only to the test process after the compose health check succeeds.

- [ ] **Step 4: Run persistence tests against Neo4j**

Run: `./scripts/test-integration.sh backend/tests/integration/test_graph_persistence.py -v`

Expected: PASS, with Neo4j removed by the cleanup trap after completion.

- [ ] **Step 5: Commit the persistence layer**

```bash
git add backend/tests/integration scripts/test-integration.sh
git commit -m "test: verify Neo4j graph persistence end to end"
```

### Task 3: Expand API and client contract hardening

**Files:**
- Modify: `backend/tests/test_routes.py`
- Modify: `frontend/src/lib/api.test.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Write failing API boundary tests**

Add cases that submit empty/oversized query input, invalid scan payloads, zero and over-limit graph arguments, missing file-detail paths, and a store exception. Assert public status codes and response bodies rather than mocked implementation calls. Add client tests asserting URL encoding, token headers, that JSON requests carry `Content-Type`, and that read-only requests do not add `Content-Type` and trigger needless cross-origin preflight.

```python
def test_graph_rejects_non_positive_and_over_limit_values() -> None:
    assert client.get("/api/graph?limit=0").status_code == 422
    assert client.get("/api/graph?edge_limit=999999").status_code == 422

def test_file_detail_requires_path_parameter() -> None:
    response = client.get("/api/file-detail")
    assert response.status_code == 422
```

```ts
it("does not send a JSON content type for a read-only request", async () => {
  await api.getRepositories();
  const [, options] = vi.mocked(fetch).mock.calls[0];
  expect(new Headers(options?.headers).get("Content-Type")).toBeNull();
});

it("encodes repository paths in graph requests", async () => {
  await api.getGraph("/repo with spaces", 80, "src/a&b");
  expect(fetch).toHaveBeenCalledWith(
    expect.stringContaining("repo_path=%2Frepo+with+spaces"),
    expect.any(Object),
  );
});
```

- [ ] **Step 2: Run the new test targets and verify they identify gaps**

Run: `cd backend && uv run pytest tests/test_routes.py -v`

Run: `cd frontend && npm run test -- src/lib/api.test.ts`

Expected: at least one test fails if the existing client does not preserve `Headers` instances or if any public boundary is underspecified.

- [ ] **Step 3: Make the minimal client or route correction required by the failing test**

Normalize `RequestInit.headers` with `new Headers(init?.headers)`, add the API token when configured, and add `Content-Type: application/json` only when a request sends a body. Do not replace valid FastAPI validation behavior; only change route code if a failing test demonstrates an incorrect public result.

```ts
const headers = new Headers(init?.headers);
if (init?.body) headers.set("Content-Type", "application/json");
if (apiToken) headers.set("X-API-Key", apiToken);
```

- [ ] **Step 4: Re-run API and client contract tests**

Run: `cd backend && uv run pytest tests/test_routes.py -v`

Run: `cd frontend && npm run test -- src/lib/api.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit contract hardening**

```bash
git add backend/tests/test_routes.py frontend/src/lib/api.ts frontend/src/lib/api.test.ts
git commit -m "test: harden API and client contracts"
```

### Task 4: Add native scanner adversarial regression coverage

**Files:**
- Modify: `backend/rust/src/discovery.rs`
- Modify: `backend/rust/src/resolver.rs`
- Modify: `backend/rust/src/scanner.rs`
- Modify: `backend/tests/test_rust_parity.py`

- [ ] **Step 1: Write failing Rust-core tests**

Add native tests for ignored directories, nested repository metadata, an outside-root symlink, Unicode filenames, and cyclic relative imports. Add one Python parity test that writes those fixtures under `tmp_path`, invokes `scan_repository`, and asserts every reported relative path stays inside the fixture root and every resolved import target exists in the returned file set.

```rust
#[test]
fn source_discovery_excludes_outside_root_symlink() {
    let root = temp_repo_with("safe.py", "x = 1\n");
    symlink("/private/outside.py", root.join("escape.py"));
    let paths = discover_source_files(&root, &ScanOptions::default()).unwrap();
    assert!(!paths.iter().any(|path| path.ends_with("escape.py")));
}
```

```python
@pytest.mark.asyncio
async def test_native_scan_keeps_paths_and_import_targets_inside_repository(tmp_path: Path) -> None:
    root = make_adversarial_repository(tmp_path)
    graph = await scan_repository(str(root))
    files = {file.path for file in graph.files}
    assert files == {"pkg/a.py", "pkg/b.py", "unicode_π.py"}
    assert all(target.target in files for target in graph.imports if target.target is not None)
```

- [ ] **Step 2: Run native and parity tests to verify failure**

Run: `cd backend/rust && cargo test discovery resolver scanner --lib`

Run: `cd backend && uv run pytest tests/test_rust_parity.py -v`

Expected: FAIL until the tests and any required containment correction are in place.

- [ ] **Step 3: Apply the smallest containment/resolution fix if a test reveals one**

Keep the existing scanner API unchanged. If discovery follows a link or resolver produces a non-repository target, canonicalize candidate paths before admitting them and reject targets that are not beneath the canonical repository root. Preserve valid Unicode paths and cyclic import edges.

- [ ] **Step 4: Verify native and Python-level behavior**

Run: `cd backend/rust && cargo test --lib`

Run: `cd backend && uv run pytest tests/test_rust_parity.py tests/test_symlink_containment.py -v`

Expected: PASS.

- [ ] **Step 5: Commit native hardening**

```bash
git add backend/rust/src backend/tests/test_rust_parity.py
git commit -m "test: harden native scanner adversarial coverage"
```

### Task 5: Add browser critical-path and failure-state coverage

**Files:**
- Create: `frontend/e2e/critical_paths.py`
- Modify: `scripts/test-e2e.sh`
- Modify: `frontend/src/app/CartographerApp.test.tsx`
- Modify: `README.md`

- [ ] **Step 1: Write the browser script with deterministic API routes**

Use native Python Playwright. Start the built frontend from `scripts/test-e2e.sh`, create a fresh browser context per case, and intercept all `/api/*` requests. Cover empty workspace, a successful scan followed by graph/file inspection, question/answer rendering, scan failure toast, and query failure toast. Capture console/page/request failures and assert none appear except the deliberately fulfilled error responses.

```python
def test_scan_then_inspect_and_ask(browser: Browser) -> None:
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    install_api_routes(page, scenario="success")
    page.goto(FRONTEND_URL)
    page.get_by_label("Repository path").fill("/fixture")
    page.get_by_role("button", name="Map repository").click()
    expect(page.get_by_text("Repository scanned successfully.")).to_be_visible()
    page.get_by_text("main.py", exact=True).click()
    expect(page.get_by_text("Symbols")).to_be_visible()
    page.get_by_placeholder("Ask about this codebase...").fill("Where is entry point?")
    page.get_by_role("button", name="Ask").click()
    expect(page.get_by_text("main.py is the entry point.")).to_be_visible()
```

- [ ] **Step 2: Run the browser script and verify it fails before the harness exists**

Run: `./scripts/test-e2e.sh`

Expected: FAIL because the script and browser scenarios do not exist.

- [ ] **Step 3: Add accessibility and layout checks**

In the browser script, assert the core controls are located by role or label, tab through the primary controls and verify visible focus, check no horizontal overflow at 390×844, 768×1024, and 1440×900, and save deterministic screenshots to `/tmp/cartographer-e2e`. Use condition-based expectations; do not use fixed sleeps except a brief layout-settle wait before a screenshot.

- [ ] **Step 4: Make only test-proven UI accessibility corrections**

If role/label locators expose an unlabeled field, missing button name, invisible focus state, or a responsive overflow, add the smallest semantic attribute or CSS correction in the owning component/style file. Add a component-level regression assertion in `CartographerApp.test.tsx` for each correction.

- [ ] **Step 5: Run browser and component coverage**

Run: `./scripts/test-e2e.sh`

Run: `cd frontend && npm run test -- src/app/CartographerApp.test.tsx`

Expected: PASS with no unexpected console, page, or failed-request errors.

- [ ] **Step 6: Commit browser coverage**

```bash
git add frontend/e2e/critical_paths.py frontend/src/app/CartographerApp.test.tsx scripts/test-e2e.sh README.md frontend/src
git commit -m "test: cover browser investigation critical paths"
```

### Task 6: Run the complete verification matrix and document it

**Files:**
- Modify: `README.md`
- Modify: `check.sh`

- [ ] **Step 1: Write the failing documentation checks**

Extend `backend/tests/test_test_commands.py` to require a README section containing the exact default, integration, browser, and optional live-provider smoke commands. Assert the default command is explicitly described as credential-free and that no live-provider command is part of `check.sh`.

```python
def test_readme_documents_each_test_tier() -> None:
    readme = README.read_text()
    for command in ("./check.sh", "./scripts/test-integration.sh", "./scripts/test-e2e.sh"):
        assert command in readme
    assert "opt-in" in readme.lower()
```

- [ ] **Step 2: Run documentation tests and verify failure**

Run: `cd backend && uv run pytest tests/test_test_commands.py -v`

Expected: FAIL until the README documents every supported tier.

- [ ] **Step 3: Document commands and final gate order**

Add a concise README “Testing” section with prerequisites, the exact commands, what each tier proves, how to install the Playwright browser, and the assurance that external AI calls are mocked. Keep `check.sh` as the normal deterministic gate; do not run integration or browser tests implicitly from it.

- [ ] **Step 4: Run the deterministic quality gate**

Run: `./check.sh`

Expected: backend tests meet the 90% coverage threshold, Ruff and MyPy pass, frontend tests meet all 85% thresholds, and TypeScript completes without errors.

- [ ] **Step 5: Run extended test tiers**

Run: `./scripts/test-integration.sh`

Run: `./scripts/test-e2e.sh`

Expected: real Neo4j persistence tests and browser critical-path tests pass, and both commands clean up their temporary services/processes.

- [ ] **Step 6: Inspect the final change set and commit**

Run: `git status --short && git diff --check && git log --oneline -6`

Expected: only intended source, test, command, and documentation changes remain; no generated coverage, browser, environment, or database files are tracked.

```bash
git add README.md check.sh backend/tests/test_test_commands.py
git commit -m "docs: document layered test verification"
```

## Plan self-review

- **Spec coverage:** Task 1 provides deterministic and opt-in commands; Task 2 proves real graph persistence; Tasks 3 and 4 cover API/client and adversarial scanner safety; Task 5 covers the interactive workflow and failure states; Task 6 executes and documents the full verification matrix.
- **No placeholder scan:** Every task names its files, verification commands, expected results, and concrete behavior. Live providers are deliberately excluded from the default and extended test paths.
- **Ordering:** Commands exist before service tests, service tests before full verification, and browser tests use the harness established in Task 1. No task depends on an undefined helper without defining its owning file.
