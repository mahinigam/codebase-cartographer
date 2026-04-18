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
    python_modules = _python_module_index(file_paths)
    js_modules = _js_module_index(file_paths)

    for edge in graph.imports:
        if edge.target.startswith("./") or edge.target.startswith("../"):
            edge.target_path = _resolve_relative_module(edge.source_path, edge.target, js_modules)
        elif edge.target.startswith("."):
            edge.target_path = _resolve_relative_python_module(
                edge.source_path, edge.target, python_modules
            )
        elif edge.target in python_modules:
            edge.target_path = python_modules[edge.target]
        elif edge.target in js_modules:
            edge.target_path = js_modules[edge.target]


def _python_module_index(file_paths: set[str]) -> dict[str, str]:
    modules: dict[str, str] = {}
    for path in sorted(file_paths, key=len):
        if not path.endswith(".py"):
            continue
        module = path[:-3].replace("/", ".")
        _add_module_aliases(modules, module, path)
        if module.endswith(".__init__"):
            _add_module_aliases(modules, module.removesuffix(".__init__"), path)
    return modules


def _add_module_aliases(modules: dict[str, str], module: str, path: str) -> None:
    parts = module.split(".")
    for index in range(len(parts)):
        alias = ".".join(parts[index:])
        modules.setdefault(alias, path)


def _js_module_index(file_paths: set[str]) -> dict[str, str]:
    modules: dict[str, str] = {}
    for path in sorted(file_paths, key=len):
        if "." not in path:
            continue
        stem = path.rsplit(".", 1)[0]
        modules.setdefault(stem, path)
        modules.setdefault(f"./{stem}", path)
    return modules


def _resolve_relative_module(source_path: str, target: str, modules: dict[str, str]) -> str | None:
    source_parent = Path(source_path).parent
    normalized = (source_parent / target).as_posix()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return modules.get(normalized)


def _resolve_relative_python_module(
    source_path: str, target: str, modules: dict[str, str]
) -> str | None:
    leading_dots = len(target) - len(target.lstrip("."))
    module_tail = target.lstrip(".")
    source_parts = Path(source_path).with_suffix("").parts
    base_parts = source_parts[: max(len(source_parts) - leading_dots, 0)]
    candidate = ".".join([*base_parts, module_tail]).strip(".")
    return modules.get(candidate)


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
