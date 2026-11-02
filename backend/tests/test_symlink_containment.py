"""Symlink containment tests.

A symlink planted inside a scanned repository must never cause content
outside the repository root to be discovered (discovery) or read
(Jev snippets, summaries).
"""

from pathlib import Path

import pytest

from app.core.config import settings
from app.indexing.discovery import source_files
from app.indexing.scanner import _safe_snippet, scan_repository
from app.services.jev_client import jev_client


@pytest.fixture
def escaped_secret(tmp_path: Path) -> Path:
    """A readable file placed OUTSIDE the repository root."""
    secret = tmp_path.parent / f"secret-{id(tmp_path)}.py"
    secret.write_text("TOKEN = 'super-secret'\n" * 50, encoding="utf-8")
    yield secret
    secret.unlink(missing_ok=True)


def test_source_files_skips_out_of_root_symlink(tmp_path: Path, escaped_secret: Path) -> None:
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "escape.py").symlink_to(escaped_secret)
    (tmp_path / "in_root_alias.py").symlink_to(tmp_path / "app.py")

    files = source_files(tmp_path)

    names = {f.name for f in files}
    assert names == {"app.py", "in_root_alias.py"}, (
        "escape symlink must be dropped from discovery; in-root alias must remain"
    )


def test_safe_snippet_blocks_out_of_root_symlink(
    tmp_path: Path, escaped_secret: Path
) -> None:
    (tmp_path / "escape.py").symlink_to(escaped_secret)

    assert _safe_snippet(tmp_path, "escape.py", 2000) == ""


def test_safe_snippet_blocks_missing_file(tmp_path: Path) -> None:
    assert _safe_snippet(tmp_path, "missing.py", 100) == ""


def test_safe_snippet_returns_bounded_in_root_content(
    tmp_path: Path, escaped_secret: Path
) -> None:
    content = "x = 1\n" * 400  # > 1000 chars
    (tmp_path / "app.py").write_text(content, encoding="utf-8")
    (tmp_path / "alias.py").symlink_to(tmp_path / "app.py")

    direct = _safe_snippet(tmp_path, "app.py", 100)
    via_alias = _safe_snippet(tmp_path, "alias.py", 100)

    assert direct == content[:100] == via_alias


@pytest.mark.asyncio
async def test_scan_repository_ignores_escape_symlink(
    tmp_path: Path, escaped_secret: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "allowed_repo_roots_raw", "")
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "escape.py").symlink_to(escaped_secret)

    graph = await scan_repository(str(tmp_path))

    paths = [file.path for file in graph.files]
    assert paths == ["app.py"]


@pytest.mark.asyncio
async def test_scan_repository_jev_snippet_is_contained(
    tmp_path: Path, escaped_secret: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Jev must never receive a snippet that escaped the root."""
    monkeypatch.setattr(settings, "allowed_repo_roots_raw", "")
    monkeypatch.setattr(jev_client, "enabled", True)
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "escape.py").symlink_to(escaped_secret)

    captured: dict[str, str] = {}
    other_calls: list[tuple] = []

    async def dummy_classify(**kwargs):
        captured[kwargs.get("file_path", "")] = kwargs.get("snippet", "unset")

    async def noop(*args, **kwargs):
        other_calls.append(args)
        return None

    monkeypatch.setattr(jev_client, "classify_file", dummy_classify)
    monkeypatch.setattr(jev_client, "score_semantic_risk", noop)
    monkeypatch.setattr(jev_client, "detect_test_file", noop)
    monkeypatch.setattr(jev_client, "detect_framework", noop)
    monkeypatch.setattr(jev_client, "detect_dead_code", noop)

    await scan_repository(str(tmp_path))

    assert captured["app.py"] == "print('hi')\n"
    assert "escape.py" not in captured, "escaped symlink must not reach Jev at all"
    assert "super-secret" not in str(captured) + str(other_calls)
