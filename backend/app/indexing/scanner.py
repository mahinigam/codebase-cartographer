import asyncio
from pathlib import Path

from app._native import RepositoryTooLargeError, safe_snippet_native, scan_repo_native
from app.core.config import settings
from app.core.errors import RepositoryTooLarge
from app.indexing.python_parser import parse_python  # noqa: F401
from app.models.graph import CachedFile, CodeFile, CodeSymbol, ImportEdge, RepositoryGraph
from app.services.jev_client import jev_client


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


async def scan_repository(
    path_text: str,
    previous_files: dict[str, CachedFile] | None = None,
    max_files: int | None = None,
) -> RepositoryGraph:
    jev_client.reset_call_budget()
    root = validate_repo_path(path_text)
    file_limit = settings.scan_max_files if max_files is None else max_files
    max_file_bytes = max(settings.scan_max_file_bytes, 0)

    try:
        native_graph = scan_repo_native(
            str(root),
            previous_files,
            max(file_limit, 0),
            max_file_bytes,
        )
    except RepositoryTooLargeError as exc:
        raise RepositoryTooLarge(str(exc)) from exc

    graph = RepositoryGraph(
        root_path=native_graph.root_path,
        name=native_graph.name,
        files=[
            CodeFile(
                path=f.path,
                language=f.language,
                loc=f.loc,
                size_bytes=f.size_bytes,
                mtime_ns=f.mtime_ns,
                content_hash=f.content_hash,
                churn_count=f.churn_count,
                last_modified=f.last_modified,
                complexity=f.complexity,
                load_bearing_score=f.load_bearing_score,
            )
            for f in native_graph.files
        ],
        symbols=[
            CodeSymbol(
                id=s.id,
                file_path=s.file_path,
                name=s.name,
                kind=s.kind,
                signature=s.signature,
                start_line=s.start_line,
                end_line=s.end_line,
                complexity=s.complexity,
            )
            for s in native_graph.symbols
        ],
        imports=[
            ImportEdge(
                source_path=i.source_path,
                target=i.target,
                target_path=i.target_path,
                line_number=i.line_number,
            )
            for i in native_graph.imports
        ],
    )

    await _classify_files_with_jev(graph, root)
    await _detect_tests_with_jev(graph, root)
    await _detect_frameworks_with_jev(graph, root)
    await _detect_dead_code_with_jev(graph, root)
    await _enhance_risk_with_jev(graph)
    return graph


def _safe_snippet(root: Path, relative: str, limit: int) -> str:
    """Read a bounded text snippet from a file inside the scanned root."""
    return safe_snippet_native(str(root), relative, limit)


def _read_source_head(path: Path, max_bytes: int) -> str:
    """Read a file, capped to ``max_bytes`` so one file can't balloon memory."""
    if max_bytes <= 0:
        return path.read_text(encoding="utf-8", errors="ignore")
    with path.open("rb") as handle:
        data = handle.read(max_bytes)
    return data.decode("utf-8", errors="ignore")


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
            snippet = _safe_snippet(root, file.path, 2000)

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

    symbols_by_file: dict[str, list[str]] = {}
    for sym in graph.symbols:
        symbols_by_file.setdefault(sym.file_path, []).append(sym.name)

    imports_by_file: dict[str, list[str]] = {}
    dependents_by_file: dict[str, list[str]] = {}
    ext_deps_by_file: dict[str, list[str]] = {}
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
    symbols_by_file: dict[str, list[str]] = {}
    for sym in graph.symbols:
        symbols_by_file.setdefault(sym.file_path, []).append(sym.name)
    imports_by_file: dict[str, list[str]] = {}
    ext_deps_by_file: dict[str, list[str]] = {}
    for edge in graph.imports:
        if edge.target_path:
            imports_by_file.setdefault(edge.source_path, []).append(edge.target_path)
        else:
            ext_deps_by_file.setdefault(edge.source_path, []).append(edge.target)

    async def detect_one(file: CodeFile) -> None:
        async with semaphore:
            snippet = _safe_snippet(root, file.path, 1500)

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
    symbols_by_file: dict[str, list[str]] = {}
    for sym in graph.symbols:
        symbols_by_file.setdefault(sym.file_path, []).append(sym.name)
    imports_by_file: dict[str, list[str]] = {}
    ext_deps_by_file: dict[str, list[str]] = {}
    for edge in graph.imports:
        if edge.target_path:
            imports_by_file.setdefault(edge.source_path, []).append(edge.target_path)
        else:
            ext_deps_by_file.setdefault(edge.source_path, []).append(edge.target)

    async def detect_one(file: CodeFile) -> None:
        async with semaphore:
            snippet = _safe_snippet(root, file.path, 1500)

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

    symbols_by_file: dict[str, list[str]] = {}
    for sym in graph.symbols:
        symbols_by_file.setdefault(sym.file_path, []).append(sym.name)
    ext_deps_by_file: dict[str, list[str]] = {}
    for edge in graph.imports:
        if not edge.target_path:
            ext_deps_by_file.setdefault(edge.source_path, []).append(edge.target)

    async def detect_one(file: CodeFile) -> None:
        async with semaphore:
            snippet = _safe_snippet(root, file.path, 1000)

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
