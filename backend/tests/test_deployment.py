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
    text = _compose_text()
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "neo4j:")
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
