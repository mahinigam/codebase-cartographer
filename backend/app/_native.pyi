from typing import Any

class RepositoryTooLargeError(ValueError): ...

class IndexedFile:
    path: str
    language: str
    loc: int
    size_bytes: int
    mtime_ns: int
    content_hash: str
    churn_count: int
    last_modified: str | None
    complexity: int
    load_bearing_score: float

class IndexedSymbol:
    id: str
    file_path: str
    name: str
    kind: str
    signature: str | None
    start_line: int
    end_line: int
    complexity: int

class IndexedImport:
    source_path: str
    target: str
    target_path: str | None
    line_number: int | None

class ScanStats:
    git_churn_ms: float
    discovery_ms: float
    parse_hash_ms: float
    resolve_score_ms: float
    total_ms: float
    cached_stat_hits: int
    cached_hash_hits: int
    parsed_files: int

class NativeRepoGraph:
    root_path: str
    name: str
    files: list[IndexedFile]
    symbols: list[IndexedSymbol]
    imports: list[IndexedImport]
    stats: ScanStats

def scan_repo_native(
    root_path: str,
    previous_files: dict[str, Any] | None = None,
    max_files: int = 0,
    max_file_bytes: int = 2_000_000,
) -> NativeRepoGraph: ...

def discover_source_files_native(root_path: str) -> list[str]: ...

def safe_snippet_native(root_path: str, relative: str, limit: int) -> str: ...

def parse_python_native(
    relative_path: str, source: str
) -> tuple[list[IndexedSymbol], list[IndexedImport], int]: ...

def parse_js_like_native(
    path: str,
    relative_path: str,
    source: str,
    language: str | None = None,
) -> tuple[list[IndexedSymbol], list[IndexedImport], int]: ...
