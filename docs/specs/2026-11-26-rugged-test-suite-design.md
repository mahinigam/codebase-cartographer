# Rugged Test Suite Design

## Goal

Protect Codebase Cartographer's core promise: transform a repository into trustworthy structural evidence that users can inspect and query, without corrupting data, escaping configured boundaries, or failing unclearly under hostile input and dependency failure.

## Scope

The test strategy will harden the existing Rust, Python, API, React, and deployment checks. It will not make live AI-provider calls part of the default suite. An explicitly opt-in smoke check may validate configured providers for deployers who choose to run it.

## Test Layers

### Fast checks

The default developer gate remains network-free and deterministic:

- Rust unit tests for parsing, discovery, dependency resolution, metrics, and containment.
- Python unit tests for configuration, orchestration, graph transformation, and provider error handling.
- FastAPI route tests for validation, authentication/configuration boundaries, response schemas, and error mapping.
- React component and client tests for rendering, interaction, accessibility-facing semantics, and API-client contracts.

### Service-backed integration checks

An opt-in integration command will use disposable services and temporary repositories to verify the complete backend data path:

1. Scan a representative repository fixture.
2. Persist files, symbols, relationships, and metrics in Neo4j.
3. Read the graph through the public API.
4. Verify idempotent rescans and cleanup/isolation between test cases.

External AI calls remain mocked. Tests assert that timeout, rate-limit, malformed-response, and unavailable-provider conditions become safe, actionable application results.

### Browser critical paths

Browser tests will run against the frontend and a controlled API fixture. They cover:

- initial, loading, empty, failure, and recovered workspace states;
- selecting a repository and completing a scan;
- graph navigation and file/risk inspection;
- architecture question submission and rendered answer/evidence;
- keyboard-operable core controls, console errors, failed requests, and responsive overflow at mobile, tablet, and desktop sizes.

## Adversarial Coverage

Each relevant layer will use fixtures for empty and large repositories, malformed or unsupported source, unusual Unicode paths, cyclic/missing imports, broken Git state, unreadable entries, nested repositories, and symlink containment attempts. API tests will include invalid and oversized payloads, missing configuration, unavailable Neo4j, and dependency timeouts. Tests will use fixed fixtures and explicit resource cleanup rather than wall-clock waits or shared mutable state.

## Execution Model

The project will expose clear commands:

- `check.sh`: deterministic unit, contract, lint, type, coverage, and build checks suitable for normal development and CI.
- an integration command: starts or targets only the required local services and runs service-backed tests.
- an E2E command: starts controlled frontend/backend instances and runs headless browser tests.
- an optional live-provider smoke command: disabled unless a deployer supplies explicit credentials and opt-in configuration.

The final delivery gate runs all applicable commands and records the actual results. Tests must not require external internet access, persistent developer data, or paid-provider credentials by default.

## Success Criteria

- A developer can run deterministic tests locally without services or API credentials.
- Service-backed checks prove graph persistence and public read paths against isolated Neo4j data.
- Browser checks prove that the user can complete the primary investigation workflow and receive clear failure feedback.
- Critical safety and failure modes have named regression tests.
- Existing behavior remains covered and all project quality gates pass before changes are declared complete.
