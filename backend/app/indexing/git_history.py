import logging
from pathlib import Path

from git import GitCommandError, InvalidGitRepositoryError, Repo
from git.exc import GitError

logger = logging.getLogger(__name__)


def file_churn(root: Path) -> dict[str, dict[str, str | int]]:
    try:
        repo = Repo(root, search_parent_directories=True)
    except (InvalidGitRepositoryError, GitCommandError, GitError, OSError, ValueError):
        return {}

    churn: dict[str, dict[str, str | int]] = {}
    try:
        for commit in repo.iter_commits(max_count=500):
            try:
                timestamp = commit.committed_datetime.isoformat()
                changed_files = commit.stats.files
            except Exception as exc:
                logger.debug(f"Skipping unreadable git commit while mining churn: {exc}")
                continue
            for file_path in changed_files:
                entry = churn.setdefault(file_path, {"count": 0, "last_modified": timestamp})
                entry["count"] = int(entry["count"]) + 1
                if str(entry["last_modified"]) < timestamp:
                    entry["last_modified"] = timestamp
    except Exception as exc:
        logger.warning(f"Git history mining stopped early: {exc}")
        return churn
    return churn
