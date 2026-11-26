import asyncio
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from app._native import parse_python_native, safe_snippet_native, scan_repo_native
from fastapi.testclient import TestClient

from app.core.config import settings
from app.indexing.scanner import UnsafeRepositoryPath, scan_repository, validate_repo_path
from app.main import app
from app.models.graph import CachedFile, CodeFile, CodeSymbol, ImportEdge
from app.services.jev_client import jev_client

GIT_BIN = shutil.which("git") or "/usr/bin/git"


def _git(repo_dir: Path, *args: str) -> None:
    subprocess.run([GIT_BIN, *args], cwd=repo_dir, check=True, capture_output=True)  # noqa: S603


def _to_cached_map(native_graph) -> dict[str, CachedFile]:
    return {
        f.path: CachedFile(
            file=CodeFile(
                path=f.path,
                language=f.language,
                loc=f.loc,
                size_bytes=f.size_bytes,
                mtime_ns=f.mtime_ns,
                content_hash=f.content_hash,
                churn_count=f.churn_count,
                last_modified=f.last_modified,
                complexity=f.complexity,
                load_bearing_score=f.load_bearing_score,
            ),
            symbols=[
                CodeSymbol(
                    id=s.id,
                    file_path=s.file_path,
                    name=s.name,
                    kind=s.kind,
                    signature=s.signature,
                    start_line=s.start_line,
                    end_line=s.end_line,
                    complexity=s.complexity,
                )
                for s in native_graph.symbols
                if s.file_path == f.path
            ],
            imports=[
                ImportEdge(
                    source_path=i.source_path,
                    target=i.target,
                    target_path=i.target_path,
                    line_number=i.line_number,
                )
                for i in native_graph.imports
                if i.source_path == f.path
            ],
        )
        for f in native_graph.files
    }


def _init_git_repo(repo_dir: Path) -> None:
    _git(repo_dir, "init")
    _git(repo_dir, "config", "user.email", "test@example.com")
    _git(repo_dir, "config", "user.name", "Tester")


def test_parse_python_native_returns_empty_on_truncated_syntax() -> None:
    symbols, imports, complexity = parse_python_native("huge.py", "def run():")
    assert symbols == []
    assert imports == []
    assert complexity == 0


def test_scan_repo_native_incremental_stat_and_hash_cache(tmp_path: Path) -> None:
    a_py = tmp_path / "a.py"
    b_ts = tmp_path / "b.ts"
    a_py.write_text("import os\ndef greet():\n    return 'hi'\n", encoding="utf-8")
    b_ts.write_text("import './a';\nexport const x = () => 1;\n", encoding="utf-8")

    cold = scan_repo_native(str(tmp_path), None, 0, 2_000_000)
    assert cold.stats.parsed_files == 2
    assert cold.stats.cached_stat_hits == 0

    previous = _to_cached_map(cold)
    warm = scan_repo_native(str(tmp_path), previous, 0, 2_000_000)
    assert warm.stats.parsed_files == 0
    assert warm.stats.cached_stat_hits == 2

    # Bump mtime with identical content -> must hit content_hash cache
    st = a_py.stat()
    os.utime(a_py, ns=(st.st_atime_ns + 1_000_000_000, st.st_mtime_ns + 1_000_000_000))
    hash_warm = scan_repo_native(str(tmp_path), previous, 0, 2_000_000)
    assert hash_warm.stats.parsed_files == 0
    assert hash_warm.stats.cached_hash_hits == 1
    assert hash_warm.stats.cached_stat_hits == 1

    # Same-length content modification -> must invalidate cache and reparse
    a_py.write_text("import os\ndef world():\n    return 'hi'\n", encoding="utf-8")
    os.utime(a_py, ns=(st.st_atime_ns + 2_000_000_000, st.st_mtime_ns + 2_000_000_000))
    reparse = scan_repo_native(str(tmp_path), previous, 0, 2_000_000)
    assert reparse.stats.parsed_files == 1
    assert any(s.name == "world" for s in reparse.symbols)


@pytest.mark.asyncio
async def test_scan_repository_real_git_churn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "allowed_repo_roots_raw", "")
    monkeypatch.setattr(jev_client, "enabled", False)
    _init_git_repo(tmp_path)

    core = tmp_path / "core.py"
    core.write_text("def run():\n    return 1\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "c1")

    core.write_text("def run():\n    return 2\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "c2")

    graph = await scan_repository(str(tmp_path))
    assert len(graph.files) == 1
    assert graph.files[0].churn_count == 2
    assert graph.files[0].last_modified is not None


@pytest.mark.asyncio
async def test_scan_repository_handles_non_utf8_crlf_and_empty_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "allowed_repo_roots_raw", "")
    monkeypatch.setattr(jev_client, "enabled", False)

    (tmp_path / "empty.py").write_text("", encoding="utf-8")
    (tmp_path / "crlf.ts").write_bytes(b"export function win() {\r\n  return 1;\r\n}\r\n")
    (tmp_path / "binary_ish.py").write_bytes(b"\xff\xfe\x00\ndef ok():\n    return 1\n")

    graph = await scan_repository(str(tmp_path))
    assert {f.path for f in graph.files} == {"empty.py", "crlf.ts", "binary_ish.py"}
    assert any(s.name == "win" for s in graph.symbols)


def test_security_path_traversal_and_allowed_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "allowed" / "proj"
    repo.mkdir(parents=True)
    (tmp_path / "outside.py").write_text("SECRET = 1\n", encoding="utf-8")

    assert safe_snippet_native(str(repo), "../../outside.py", 100) == ""

    monkeypatch.setattr(settings, "allowed_repo_roots_raw", str(tmp_path / "allowed"))
    assert validate_repo_path(str(repo)) == repo.resolve()
    with pytest.raises(UnsafeRepositoryPath):
        validate_repo_path(str(tmp_path))


@pytest.mark.asyncio
async def test_scan_repository_does_not_starve_event_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "allowed_repo_roots_raw", "")
    monkeypatch.setattr(jev_client, "enabled", False)
    for i in range(40):
        (tmp_path / f"mod_{i}.py").write_text(
            f"def fn_{i}(x):\n    if x:\n        return x\n    return 0\n",
            encoding="utf-8",
        )

    ticks = 0

    async def heartbeat() -> None:
        nonlocal ticks
        for _ in range(5):
            ticks += 1
            await asyncio.sleep(0)

    graph, _ = await asyncio.gather(scan_repository(str(tmp_path)), heartbeat())
    assert len(graph.files) == 40
    assert ticks == 5


def test_api_scan_endpoint_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from contextlib import contextmanager

    from app.api import routes

    saved = {}

    class FakeStore:
        def check_repository_cap(self, _root: str) -> None:
            return None

        def scan_cache(self, _root: str):
            return {}

        def upsert_repository_graph(self, graph) -> None:
            saved["graph"] = graph

        def overview(self, repo_path: str | None = None) -> dict:
            g = saved["graph"]
            return {"files": len(g.files), "symbols": len(g.symbols), "repo_path": repo_path}

    @contextmanager
    def fake_neo4j_store():
        yield FakeStore()

    monkeypatch.setattr(routes, "neo4j_store", fake_neo4j_store)
    monkeypatch.setattr(settings, "allowed_repo_roots_raw", "")
    monkeypatch.setattr(settings, "api_token", None)
    monkeypatch.setattr(jev_client, "enabled", False)
    _init_git_repo(tmp_path)
    (tmp_path / "main.py").write_text("def main():\n    return 42\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")

    with TestClient(app) as client:
        resp = client.post("/api/scan", json={"path": str(tmp_path), "incremental": False})
        assert resp.status_code == 200
        body = resp.json()
        assert body["overview"]["files"] == 1
        assert body["overview"]["symbols"] == 1
        assert saved["graph"].files[0].churn_count == 1

        missing = client.post("/api/scan", json={"path": str(tmp_path / "nope")})
        assert missing.status_code == 400
