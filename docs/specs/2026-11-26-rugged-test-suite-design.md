# Rugged Test Suite Completion Design

## Goal

Protect Codebase Cartographer's core promise: scan repositories into trustworthy structural evidence, persist and expose that evidence correctly, and keep the investigation workflow understandable when inputs or dependencies fail.

The existing layered test-suite work is a foundation, not a finished all-angles regression suite. This design completes its missing execution and coverage layers without changing production behavior unless a test demonstrates a real defect.

## Principles

- Keep the default local gate deterministic, service-free, and credential-free.
- Run real Neo4j and browser checks in separate GitHub Actions jobs on pushes to `main` and pull requests; do not make `check.sh` start services.
- Mock AI providers in normal, integration, and browser tests.
- Keep any paid/live provider smoke test explicitly opt-in, local-only, bounded, and incapable of running accidentally.
- Prefer observable public behavior and failure outcomes over implementation-detail assertions.
- Use temporary repositories, isolated disposable services, deterministic fixtures, bounded waits, and guaranteed cleanup.
- Preserve existing public APIs and user behavior; make only narrowly necessary production fixes exposed by tests.

## Test Layers

### Default quality gate

`bash ./check.sh` remains the fast local command and CI's unit/contract job. It covers backend pytest with the existing coverage floor, Ruff, mypy, frontend Vitest coverage, and TypeScript. It must also run the Rust crate's unit tests so native parser, discovery, resolver, and Git-history tests are not silently omitted. It must not require Docker, Chromium, external network services, or provider credentials.

### Neo4j integration

The separate integration command owns a disposable Neo4j service and always removes its containers and volumes, including after test failures. Tests use temporary repositories and the production scanner/store path, then verify persisted graph data through the public read path, idempotent rescans, stale-data removal, and cleanup/isolation. Add relevant failure assertions only where they can be deterministic without damaging developer data. External AI calls remain disabled or mocked.

GitHub Actions runs this command in an independent job. The ordinary quality job remains independently runnable and reports failures separately.

### Browser end-to-end

The separate E2E command builds and starts the production frontend locally and runs Chromium against deterministic, intercepted API responses. Cover:

- initial empty and loading states;
- successful repository scan, graph/file/risk inspection, and question/answer display;
- scan, graph/file, and question failures followed by a recoverable successful action;
- unexpected page errors and failed requests;
- keyboard access to primary actions and visible focus;
- no horizontal overflow at mobile, tablet, and desktop viewport sizes.

All API routes are intercepted; the browser suite must not depend on a live backend, database, or AI provider. GitHub Actions runs it in an independent job with the required browser installed.

### Live-provider smoke

An explicitly invoked local smoke check may make one bounded request to a provider selected through the application's existing configuration. It must require an explicit opt-in flag and the provider's configured credentials, never run in default checks or CI, avoid printing secrets or full provider responses, and state clearly that a real external call (and possible cost) will occur. If no safe provider-independent entry point exists, document that limitation rather than duplicating provider setup logic.

## CI and Commands

GitHub Actions runs three independent jobs for pushes to `main` and pull requests:

1. Default quality gate (`bash ./check.sh`).
2. Neo4j integration (`./scripts/test-integration.sh`).
3. Browser E2E (`./scripts/test-e2e.sh`).

Local extended commands remain opt-in and independently runnable. The default gate never invokes either extended script.

## Completion Criteria

- Rust unit tests execute in the default quality gate.
- The default gate passes without Docker, a browser install, network dependencies, or provider credentials.
- Integration assertions exercise persisted data and public reads, and the isolated service is cleaned up on both success and failure.
- Browser assertions cover the specified happy, empty/loading, failure/recovery, keyboard, and viewport behaviors using intercepted API fixtures.
- Both extended jobs run in CI and are also reproducible locally through their documented commands.
- Provider smoke calls are opt-in only and never run during CI.
- The full local verification matrix passes, with expected skips and any environmental limitations reported explicitly.
- Documentation and the implementation checklist accurately distinguish completed, optional, and non-run checks.

## Non-goals

- Changing production APIs or user-facing functionality without a test-proven defect.
- Requiring paid-provider access for development or CI.
- Making every optional test part of the default `check.sh`.
- Maximizing line coverage at the expense of meaningful behavioral assertions.
