from pathlib import Path

from app._native import discover_source_files_native

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
    return [Path(p) for p in discover_source_files_native(str(root))]


def language_for(path: Path) -> str:
    return LANGUAGE_BY_SUFFIX.get(path.suffix, "unknown")


def safe_relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()

