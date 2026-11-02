from pathlib import Path

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".next",
    ".turbo",
    "coverage",
}

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}


def source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    root_resolved = root.resolve()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.suffix not in LANGUAGE_BY_SUFFIX:
            continue
        if _escapes_root(path, root_resolved):
            continue
        files.append(path)
    return sorted(files)


def _escapes_root(path: Path, root_resolved: Path) -> bool:
    """True when a symlinked file resolves outside the scanned root."""
    if not path.is_symlink():
        return False
    try:
        return not path.resolve().is_relative_to(root_resolved)
    except OSError:
        # Unresolvable symlink: skip rather than risk an escape read.
        return True


def language_for(path: Path) -> str:
    return LANGUAGE_BY_SUFFIX.get(path.suffix, "unknown")


def safe_relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()

