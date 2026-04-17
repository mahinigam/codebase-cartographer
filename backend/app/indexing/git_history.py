from pathlib import Path

from git import InvalidGitRepositoryError, Repo


def file_churn(root: Path) -> dict[str, dict[str, str | int]]:
    try:
        repo = Repo(root, search_parent_directories=True)
    except InvalidGitRepositoryError:
        return {}

    churn: dict[str, dict[str, str | int]] = {}
    try:
        for commit in repo.iter_commits(max_count=500):
            timestamp = commit.committed_datetime.isoformat()
            for file_path in commit.stats.files:
                entry = churn.setdefault(file_path, {"count": 0, "last_modified": timestamp})
                entry["count"] = int(entry["count"]) + 1
                if str(entry["last_modified"]) < timestamp:
                    entry["last_modified"] = timestamp
    except ValueError:
        return {}
    return churn
