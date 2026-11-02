"""Deployment guard tests.

These pin the security posture of the committed deployment files:

* Neo4j must not accept a committed credential — the compose file has to
  fail fast when ``NEO4J_PASSWORD`` is unset.
* The Neo4j admin plane (Browser 7474, Bolt 7687) must only be published on
  loopback, never on all interfaces.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE = REPO_ROOT / "docker-compose.yml"
ENV_EXAMPLE = REPO_ROOT / ".env.example"


def _compose_text() -> str:
    assert COMPOSE.exists(), "docker-compose.yml is missing from the repository root"
    return COMPOSE.read_text()


def _neo4j_service_text() -> str:
    """Extract the ``neo4j`` service block from the compose file."""
    return _service_text("neo4j")


def _service_text(name: str) -> str:
    """Extract one top-level service block from the compose file."""
    text = _compose_text()
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == f"{name}:")
    end = next(
        (
            i
            for i, line in enumerate(lines[start + 1 :], start + 1)
            if line and not line[0].isspace()
        ),
        len(lines),
    )
    return "\n".join(lines[start:end])


def test_neo4j_ports_are_loopback_only() -> None:
    ports = [
        line.strip()
        for line in _neo4j_service_text().splitlines()
        if "7474" in line or "7687" in line
    ]
    mappings = [line for line in ports if line.startswith("- ")]
    assert mappings, "expected published Neo4j ports in docker-compose.yml"
    for mapping in mappings:
        host_side = mapping.lstrip("- ").strip().strip('"')
        assert host_side.startswith("127.0.0.1:"), (
            f"Neo4j port mapping {mapping!r} is published beyond loopback"
        )


def test_neo4j_compose_has_no_committed_credential() -> None:
    service = _neo4j_service_text()
    assert "NEO4J_AUTH" in service
    assert "${NEO4J_PASSWORD:" in service, (
        "NEO4J_AUTH must fail fast on an unset NEO4J_PASSWORD"
    )
    auth_line = next(line for line in service.splitlines() if "NEO4J_AUTH" in line)
    assert "codebase-cartographer" not in auth_line, (
        "docker-compose.yml must not ship a literal Neo4j password"
    )


def test_env_example_ships_no_neo4j_password() -> None:
    assert ENV_EXAMPLE.exists(), ".env.example is missing from the repository root"
    for line in ENV_EXAMPLE.read_text().splitlines():
        if line.startswith("NEO4J_PASSWORD="):
            assert line.strip() == "NEO4J_PASSWORD=", (
                ".env.example must not carry a default Neo4j password"
            )
            break
    else:
        raise AssertionError("expected a NEO4J_PASSWORD entry in .env.example")


# ── Hardening for non-dev deployments ──────────────────────────────────────


def test_app_plane_ports_default_to_loopback() -> None:
    """Backend/frontend must default to loopback via HOST_BIND interpolation."""
    for service, port in (("backend", "8000"), ("frontend", "5173")):
        service_text = _service_text(service)
        port_lines = [
            line.strip() for line in service_text.splitlines() if f"{port}" in line
        ]
        mappings = [line for line in port_lines if line.startswith("- ")]
        assert mappings, f"expected a published {port} mapping on {service}"
        mapping = mappings[0].lstrip("- ").strip().strip('"')
        assert mapping == "${HOST_BIND:-127.0.0.1}:" + f"{port}:{port}", (
            f"{service} {port} must default to loopback via "
            f"${{HOST_BIND:-127.0.0.1}} interpolation, found {mapping!r}"
        )


def test_env_example_documents_host_bind() -> None:
    text = ENV_EXAMPLE.read_text()
    assert "HOST_BIND=" in text, ".env.example must document HOST_BIND"
    assert "127.0.0.1" in text, "HOST_BIND default must be loopback"


def test_every_service_has_a_healthcheck() -> None:
    for service in ("neo4j", "backend", "frontend"):
        service_text = _service_text(service)
        assert "healthcheck:" in service_text, f"{service} lacks a healthcheck"
        assert "test:" in service_text, f"{service} healthcheck lacks a test"
        assert "interval:" in service_text, f"{service} healthcheck lacks an interval"


def test_boot_order_waits_for_healthy_dependencies() -> None:
    """backend waits for a healthy neo4j; frontend waits for a healthy backend."""
    backend = _service_text("backend")
    frontend = _service_text("frontend")

    assert "condition: service_healthy" in backend, (
        "backend must gate on neo4j service_healthy"
    )
    assert "neo4j:" in backend
    assert "condition: service_healthy" in frontend, (
        "frontend must gate on backend service_healthy"
    )
    assert "backend:" in frontend
    # Simple list-form depends_on cannot express the condition.
    for service_text, name in ((backend, "backend"), (frontend, "frontend")):
        depends_block = next(
            (line for line in service_text.splitlines() if "depends_on:" in line),
            "",
        )
        assert depends_block.endswith("depends_on:"), (
            f"{name} depends_on must use mapping form (condition support)"
        )


def test_app_containers_have_no_new_privileges() -> None:
    for service in ("backend", "frontend"):
        service_text = _service_text(service)
        assert "no-new-privileges:true" in service_text.replace(" ", ""), (
            f"{service} must set security_opt no-new-privileges:true"
        )


def test_health_endpoint_is_token_free() -> None:
    """Container/liveness probes must keep working when API_TOKEN is set."""
    routes = (REPO_ROOT / "backend" / "app" / "api" / "routes.py").read_text()
    main = (REPO_ROOT / "backend" / "app" / "main.py").read_text()

    assert "health_router = APIRouter()" in routes, (
        "/api/health must live on a dependency-free router"
    )
    # The token-gated router must NOT carry the health endpoint.
    router_block = routes.split("router = APIRouter(dependencies=", 1)[1]
    assert '@router.get("/health")' not in router_block, (
        "/api/health must not require an API token"
    )
    assert "health_router" in main, "main.py must include the token-free health_router"

