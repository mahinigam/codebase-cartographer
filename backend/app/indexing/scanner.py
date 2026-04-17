from pathlib import Path

from app.core.config import settings
from app.indexing.discovery import language_for, safe_relative, source_files
from app.indexing.git_history import file_churn
from app.indexing.js_parser import parse_js_like
from app.indexing.python_parser import parse_python
from app.models.graph import CodeFile, RepositoryGraph


class UnsafeRepositoryPath(ValueError):
    pass


def validate_repo_path(path_text: str) -> Path:
    root = Path(path_text).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise UnsafeRepositoryPath("Repository path must be an existing directory.")

    allowed_roots = [Path(item).expanduser().resolve() for item in settings.allowed_repo_roots]
    if allowed_roots and not any(
        root == allowed or root.is_relative_to(allowed) for allowed in allowed_roots
    ):
        raise UnsafeRepositoryPath("Repository path is outside configured allowed roots.")
    return root


def scan_repository(path_text: str) -> RepositoryGraph:
    root = validate_repo_path(path_text)
    churn = file_churn(root)
    graph = RepositoryGraph(root_path=str(root), name=root.name)

    for path in source_files(root):
        relative = safe_relative(path, root)
        source = path.read_text(encoding="utf-8", errors="ignore")
        language = language_for(path)
        loc = len([line for line in source.splitlines() if line.strip()])

        if language == "python":
            symbols, imports, complexity = parse_python(path, relative, source)
        elif language in {"javascript", "typescript"}:
            symbols, imports, complexity = parse_js_like(path, relative, source)
        else:
            symbols, imports, complexity = [], [], 0

        history = churn.get(relative, {})
        graph.files.append(
            CodeFile(
                path=relative,
                language=language,
                loc=loc,
                churn_count=int(history.get("count", 0)),
                last_modified=history.get("last_modified"),
                complexity=complexity,
            )
        )
        graph.symbols.extend(symbols)
        graph.imports.extend(imports)

    _resolve_imports(graph)
    _score_load_bearing_files(graph)
    return graph


def _resolve_imports(graph: RepositoryGraph) -> None:
    file_paths = {item.path for item in graph.files}
    python_modules = {
        path[:-3].replace("/", "."): path for path in file_paths if path.endswith(".py")
    }
    js_modules = {path.rsplit(".", 1)[0]: path for path in file_paths if "." in path}

    for edge in graph.imports:
        if edge.target.startswith("."):
            continue
        if edge.target in python_modules:
            edge.target_path = python_modules[edge.target]
        elif edge.target in js_modules:
            edge.target_path = js_modules[edge.target]
        elif edge.target.startswith("./") or edge.target.startswith("../"):
            source_parent = Path(edge.source_path).parent
            candidate = (source_parent / edge.target).as_posix()
            edge.target_path = next(
                (path for path in file_paths if path.startswith(candidate)), None
            )


def _score_load_bearing_files(graph: RepositoryGraph) -> None:
    fan_in = {file.path: 0 for file in graph.files}
    fan_out = {file.path: 0 for file in graph.files}
    for edge in graph.imports:
        fan_out[edge.source_path] = fan_out.get(edge.source_path, 0) + 1
        if edge.target_path:
            fan_in[edge.target_path] = fan_in.get(edge.target_path, 0) + 1

    max_complexity = max((file.complexity for file in graph.files), default=1) or 1
    max_churn = max((file.churn_count for file in graph.files), default=1) or 1
    max_fan_in = max(fan_in.values(), default=1) or 1

    for file in graph.files:
        file.load_bearing_score = round(
            100
            * (
                0.45 * (fan_in.get(file.path, 0) / max_fan_in)
                + 0.25 * (file.complexity / max_complexity)
                + 0.2 * (file.churn_count / max_churn)
                + 0.1 * min(fan_out.get(file.path, 0) / 10, 1)
            ),
            2,
        )
