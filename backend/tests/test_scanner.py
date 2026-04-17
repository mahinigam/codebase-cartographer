from pathlib import Path

import pytest

from app.core.config import settings
from app.indexing.scanner import UnsafeRepositoryPath, scan_repository, validate_repo_path


def test_validate_repo_path_rejects_missing_path() -> None:
    with pytest.raises(UnsafeRepositoryPath):
        validate_repo_path("/definitely/not/a/real/repo")


def test_scan_repository_scores_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "allowed_repo_roots_raw", "")
    module = tmp_path / "service.py"
    module.write_text(
        """
import json

def load(value):
    if value:
        return json.loads(value)
    return {}
""",
        encoding="utf-8",
    )

    graph = scan_repository(str(tmp_path))

    assert len(graph.files) == 1
    assert len(graph.symbols) == 1
    assert graph.files[0].load_bearing_score > 0
