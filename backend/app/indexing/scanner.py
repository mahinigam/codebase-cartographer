import hashlib
import os
from pathlib import Path

import asyncio
from app.core.config import settings
from app.services.jev_client import jev_client
from app.indexing.discovery import language_for, safe_relative, source_files
from app.indexing.git_history import file_churn
from app.indexing.js_parser import parse_js_like
from app.indexing.python_parser import parse_python
from app.models.graph import CachedFile, CodeFile, RepositoryGraph


class UnsafeRepositoryPath(ValueError):
    pass


class RepositoryTooLarge(ValueError):
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


async def scan_repository(
    path_text: str,
    previous_files: dict[str, CachedFile] | None = None,
    max_files: int | None = None,
) -> RepositoryGraph:
    root = validate_repo_path(path_text)
    churn = file_churn(root)
    graph = RepositoryGraph(root_path=str(root), name=root.name)
    paths = source_files(root)
    file_limit = settings.scan_max_files if max_files is None else max_files
    if file_limit > 0 and len(paths) > file_limit:
        raise RepositoryTooLarge(
            f"Repository has {len(paths)} supported source files; limit is {file_limit}."
        )

    for path in paths:
        relative = safe_relative(path, root)
        stat = path.stat()
        language = language_for(path)
        cached = previous_files.get(relative) if previous_files else None
        source: str | None = None
        content_hash: str | None = None

        if cached and _same_stat_fingerprint(cached.file, stat):
            _append_cached_file(graph, cached, churn.get(relative, {}), stat)
            continue

        source = path.read_text(encoding="utf-8", errors="ignore")
        content_hash = _content_hash(source)
        if cached and cached.file.content_hash == content_hash:
            _append_cached_file(graph, cached, churn.get(relative, {}), stat, content_hash)
            continue

        loc = len([line for line in source.splitlines() if line.strip()])

        if language == "python":
            symbols, imports, complexity = parse_python(path, relative, source)
        elif language in {"javascript", "typescript"}:
            symbols, imports, complexity = parse_js_like(path, relative, source, language)
        else:
            symbols, imports, complexity = [], [], 0

        history = churn.get(relative, {})
        graph.files.append(
            CodeFile(
                path=relative,
                language=language,
                loc=loc,
                size_bytes=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
                content_hash=content_hash,
                churn_count=int(history.get("count", 0)),
                last_modified=history.get("last_modified"),
                complexity=complexity,
            )
        )
        graph.symbols.extend(symbols)
        graph.imports.extend(imports)

    _resolve_imports(graph)
    _score_load_bearing_files(graph)
    await _classify_files_with_jev(graph, root)
    await _detect_tests_with_jev(graph, root)
    await _detect_frameworks_with_jev(graph, root)
    await _detect_dead_code_with_jev(graph, root)
    await _enhance_risk_with_jev(graph)
    return graph


def _same_stat_fingerprint(file: CodeFile, stat: os.stat_result) -> bool:
    return (
        file.content_hash is not None
        and file.size_bytes == stat.st_size
        and file.mtime_ns == stat.st_mtime_ns
    )


def _content_hash(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8", errors="ignore")).hexdigest()


def _append_cached_file(
    graph: RepositoryGraph,
    cached: CachedFile,
    history: dict[str, str | int],
    stat: os.stat_result,
    content_hash: str | None = None,
) -> None:
    file = cached.file.model_copy(
        update={
            "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "content_hash": content_hash or cached.file.content_hash,
            "churn_count": int(history.get("count", cached.file.churn_count)),
            "last_modified": history.get("last_modified", cached.file.last_modified),
        }
    )
    graph.files.append(file)
    graph.symbols.extend(cached.symbols)
    graph.imports.extend(cached.imports)


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


_JS_SUFFIXES = (".tsx", ".ts", ".jsx", ".js", ".mjs", ".cjs")


def _resolve_relative_module(source_path: str, target: str, modules: dict[str, str]) -> str | None:
    source_parent = Path(source_path).parent
    normalized = Path(os.path.normpath(source_parent / target)).as_posix()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized == ".." or normalized.startswith("../"):
        return None
    return _lookup_js_module(normalized, modules)


def _lookup_js_module(normalized: str, modules: dict[str, str]) -> str | None:
    stems = [normalized]
    for suffix in _JS_SUFFIXES:
        if normalized.endswith(suffix):
            stems.append(normalized[: -len(suffix)])
            break
    for stem in stems:
        for candidate in (stem, f"{stem}/index"):
            resolved = modules.get(candidate)
            if resolved:
                return resolved
    return None


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
        fan_in_score = fan_in.get(file.path, 0) / max_fan_in
        # Dampen fan-in weight for trivial utility files (small + simple).
        # Without this, a 10-line re-export or UI atom imported everywhere
        # would outrank genuinely load-bearing modules.
        if file.loc < 30 and file.complexity <= 1:
            fan_in_score *= 0.3
        file.load_bearing_score = round(
            100
            * (
                0.45 * fan_in_score
                + 0.25 * (file.complexity / max_complexity)
                + 0.2 * (file.churn_count / max_churn)
                + 0.1 * min(fan_out.get(file.path, 0) / 10, 1)
            ),
            2,
        )


async def _classify_files_with_jev(graph: RepositoryGraph, root: Path) -> None:
    """Bond 1: Classify every file's architectural role using Jev."""
    if not jev_client.enabled:
        return

    semaphore = asyncio.Semaphore(settings.jev_batch_concurrency)

    # Precompute fan_in / fan_out per file
    fan_in_map: dict[str, int] = {f.path: 0 for f in graph.files}
    fan_out_map: dict[str, int] = {f.path: 0 for f in graph.files}
    for edge in graph.imports:
        fan_out_map[edge.source_path] = fan_out_map.get(edge.source_path, 0) + 1
        if edge.target_path:
            fan_in_map[edge.target_path] = fan_in_map.get(edge.target_path, 0) + 1

    # Build symbol index
    symbols_by_file: dict[str, list[str]] = {}
    for sym in graph.symbols:
        symbols_by_file.setdefault(sym.file_path, []).append(sym.name)

    # Build import index
    imports_by_file: dict[str, list[str]] = {}
    ext_deps_by_file: dict[str, list[str]] = {}
    for edge in graph.imports:
        if edge.target_path:
            imports_by_file.setdefault(edge.source_path, []).append(edge.target_path)
        else:
            ext_deps_by_file.setdefault(edge.source_path, []).append(edge.target)

    async def classify_one(file: CodeFile) -> None:
        async with semaphore:
            # Read snippet for context
            snippet = ""
            try:
                full_path = root / file.path
                if full_path.exists():
                    snippet = full_path.read_text(encoding="utf-8", errors="ignore")[:2000]
            except Exception:
                pass

            result = await jev_client.classify_file(
                file_path=file.path,
                language=file.language,
                loc=file.loc,
                complexity=file.complexity,
                fan_in=fan_in_map.get(file.path, 0),
                fan_out=fan_out_map.get(file.path, 0),
                symbols=symbols_by_file.get(file.path, []),
                imports=imports_by_file.get(file.path, []),
                external_deps=ext_deps_by_file.get(file.path, []),
                snippet=snippet,
            )
            if result:
                role_decision = result.get("architectural_role")
                if role_decision:
                    file.architectural_role = role_decision.answer
                    file.architectural_role_confidence = role_decision.confidence

    await asyncio.gather(*(classify_one(f) for f in graph.files))


async def _enhance_risk_with_jev(graph: RepositoryGraph) -> None:
    """Bond 2: Enhance deterministic risk scores with Jev semantic scoring."""
    if not jev_client.enabled:
        return

    # Only score files with deterministic score > 20 (skip trivial files)
    candidates = [f for f in graph.files if f.load_bearing_score > 20]
    semaphore = asyncio.Semaphore(settings.jev_batch_concurrency)

    # Reuse precomputed maps from Bond 1
    fan_in_map = {f.path: 0 for f in graph.files}
    fan_out_map = {f.path: 0 for f in graph.files}
    for edge in graph.imports:
        fan_out_map[edge.source_path] = fan_out_map.get(edge.source_path, 0) + 1
        if edge.target_path:
            fan_in_map[edge.target_path] = fan_in_map.get(edge.target_path, 0) + 1

    symbols_by_file = {}
    for sym in graph.symbols:
        symbols_by_file.setdefault(sym.file_path, []).append(sym.name)

    imports_by_file = {}
    dependents_by_file = {}
    ext_deps_by_file = {}
    for edge in graph.imports:
        if edge.target_path:
            imports_by_file.setdefault(edge.source_path, []).append(edge.target_path)
            dependents_by_file.setdefault(edge.target_path, []).append(edge.source_path)
        else:
            ext_deps_by_file.setdefault(edge.source_path, []).append(edge.target)

    async def score_one(file: CodeFile) -> None:
        async with semaphore:
            result = await jev_client.score_semantic_risk(
                file_path=file.path,
                language=file.language,
                loc=file.loc,
                complexity=file.complexity,
                fan_in=fan_in_map.get(file.path, 0),
                fan_out=fan_out_map.get(file.path, 0),
                churn_count=file.churn_count,
                symbols=symbols_by_file.get(file.path, []),
                imports=imports_by_file.get(file.path, []),
                dependents=dependents_by_file.get(file.path, []),
                external_deps=ext_deps_by_file.get(file.path, []),
                deterministic_score=file.load_bearing_score,
            )
            if result:
                risk_dec = result.get("semantic_risk")
                cat_dec = result.get("risk_category")
                if risk_dec and risk_dec.value is not None:
                    # Normalize Jev's 1-10 scale to 0-100
                    jev_normalized = (risk_dec.value - 1) / 9 * 100
                    # Blend: 70% deterministic + 30% semantic
                    file.load_bearing_score = round(
                        0.7 * file.load_bearing_score + 0.3 * jev_normalized, 2
                    )
                    file.semantic_risk_score = round(risk_dec.value, 2)
                if cat_dec:
                    file.risk_category = cat_dec.answer

    await asyncio.gather(*(score_one(f) for f in candidates))


async def _detect_tests_with_jev(graph: RepositoryGraph, root: Path) -> None:
    """Bond 3: Probabilistic test file detection."""
    if not jev_client.enabled:
        return

    semaphore = asyncio.Semaphore(settings.jev_batch_concurrency)
    symbols_by_file = {}
    for sym in graph.symbols:
        symbols_by_file.setdefault(sym.file_path, []).append(sym.name)
    imports_by_file = {}
    ext_deps_by_file = {}
    for edge in graph.imports:
        if edge.target_path:
            imports_by_file.setdefault(edge.source_path, []).append(edge.target_path)
        else:
            ext_deps_by_file.setdefault(edge.source_path, []).append(edge.target)

    async def detect_one(file: CodeFile) -> None:
        async with semaphore:
            snippet = ""
            try:
                full_path = root / file.path
                if full_path.exists():
                    snippet = full_path.read_text(encoding="utf-8", errors="ignore")[:1500]
            except Exception:
                pass

            result = await jev_client.detect_test_file(
                file_path=file.path,
                language=file.language,
                symbols=symbols_by_file.get(file.path, []),
                imports=imports_by_file.get(file.path, []),
                external_deps=ext_deps_by_file.get(file.path, []),
                snippet=snippet,
            )
            if result:
                test_dec = result.get("is_test")
                cat_dec = result.get("test_category")
                if test_dec:
                    file.is_test_probability = test_dec.probability or 0.0
                    file.is_test_file = file.is_test_probability > 0.6
                if cat_dec:
                    file.test_category = cat_dec.answer

    await asyncio.gather(*(detect_one(f) for f in graph.files))


async def _detect_frameworks_with_jev(graph: RepositoryGraph, root: Path) -> None:
    """Bond 8: Detect framework ecosystem for each file."""
    if not jev_client.enabled:
        return

    semaphore = asyncio.Semaphore(settings.jev_batch_concurrency)
    symbols_by_file = {}
    for sym in graph.symbols:
        symbols_by_file.setdefault(sym.file_path, []).append(sym.name)
    imports_by_file = {}
    ext_deps_by_file = {}
    for edge in graph.imports:
        if edge.target_path:
            imports_by_file.setdefault(edge.source_path, []).append(edge.target_path)
        else:
            ext_deps_by_file.setdefault(edge.source_path, []).append(edge.target)

    async def detect_one(file: CodeFile) -> None:
        async with semaphore:
            snippet = ""
            try:
                full_path = root / file.path
                if full_path.exists():
                    snippet = full_path.read_text(encoding="utf-8", errors="ignore")[:1500]
            except Exception:
                pass

            result = await jev_client.detect_framework(
                file_path=file.path,
                language=file.language,
                imports=imports_by_file.get(file.path, []),
                external_deps=ext_deps_by_file.get(file.path, []),
                symbols=symbols_by_file.get(file.path, []),
                snippet=snippet,
            )
            if result:
                fw = result.get("framework")
                layer = result.get("layer")
                if fw:
                    file.framework = fw.answer
                    file.framework_confidence = fw.confidence
                if layer:
                    file.architecture_layer = layer.answer

    await asyncio.gather(*(detect_one(f) for f in graph.files))


async def _detect_dead_code_with_jev(graph: RepositoryGraph, root: Path) -> None:
    """Bond 10: Detect likely dead code files."""
    if not jev_client.enabled:
        return

    # Only check files with zero fan-in (candidates for dead code)
    fan_in_map = {f.path: 0 for f in graph.files}
    for edge in graph.imports:
        if edge.target_path:
            fan_in_map[edge.target_path] = fan_in_map.get(edge.target_path, 0) + 1

    candidates = [f for f in graph.files if fan_in_map.get(f.path, 0) == 0]
    if not candidates:
        return

    semaphore = asyncio.Semaphore(settings.jev_batch_concurrency)
    fan_out_map = {f.path: 0 for f in graph.files}
    for edge in graph.imports:
        fan_out_map[edge.source_path] = fan_out_map.get(edge.source_path, 0) + 1

    symbols_by_file = {}
    for sym in graph.symbols:
        symbols_by_file.setdefault(sym.file_path, []).append(sym.name)
    ext_deps_by_file = {}
    for edge in graph.imports:
        if not edge.target_path:
            ext_deps_by_file.setdefault(edge.source_path, []).append(edge.target)

    async def detect_one(file: CodeFile) -> None:
        async with semaphore:
            snippet = ""
            try:
                full_path = root / file.path
                if full_path.exists():
                    snippet = full_path.read_text(encoding="utf-8", errors="ignore")[:1000]
            except Exception:
                pass

            result = await jev_client.detect_dead_code(
                file_path=file.path,
                language=file.language,
                loc=file.loc,
                fan_in=0,
                fan_out=fan_out_map.get(file.path, 0),
                churn_count=file.churn_count,
                last_modified=file.last_modified,
                symbols=symbols_by_file.get(file.path, []),
                external_deps=ext_deps_by_file.get(file.path, []),
                snippet=snippet,
            )
            if result:
                dead_dec = result.get("is_dead_code")
                cat_dec = result.get("dead_code_category")
                if dead_dec:
                    file.is_dead_code_probability = dead_dec.probability or 0.0
                    file.is_dead_code = file.is_dead_code_probability > 0.65
                if cat_dec:
                    file.dead_code_category = cat_dec.answer

    await asyncio.gather(*(detect_one(f) for f in candidates))
