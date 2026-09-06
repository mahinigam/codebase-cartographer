from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from git import GitCommandError

from app.indexing.git_history import file_churn


def test_file_churn_returns_empty_outside_git(tmp_path: Path) -> None:
    assert file_churn(tmp_path) == {}


def test_file_churn_returns_empty_when_repo_open_fails(
    tmp_path: Path, monkeypatch
) -> None:
    def boom(*_args, **_kwargs):
        raise GitCommandError(["git"], 128)

    monkeypatch.setattr("app.indexing.git_history.Repo", boom)
    assert file_churn(tmp_path) == {}


def test_file_churn_skips_corrupt_commits_and_keeps_valid_ones(
    tmp_path: Path, monkeypatch
) -> None:
    class BrokenCommit:
        committed_datetime = datetime(2024, 1, 1, tzinfo=UTC)

        @property
        def stats(self):
            raise GitCommandError(["git", "diff-tree"], 128)

    good_commit = SimpleNamespace(
        committed_datetime=datetime(2024, 2, 1, tzinfo=UTC),
        stats=SimpleNamespace(files={"backend/app/indexing/scanner.py": {"insertions": 4}}),
    )

    class FakeRepo:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def iter_commits(self, max_count=500):
            yield BrokenCommit()
            yield good_commit

    monkeypatch.setattr("app.indexing.git_history.Repo", FakeRepo)
    result = file_churn(tmp_path)

    assert result["backend/app/indexing/scanner.py"]["count"] == 1
