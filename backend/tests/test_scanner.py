import os
from pathlib import Path

import pytest

from app.core.config import settings
from app.indexing.scanner import (
    CachedFile,
    RepositoryTooLarge,
    UnsafeRepositoryPath,
    scan_repository,
    validate_repo_path,
)



@pytest.fixture(autouse=True)
def mock_jev_responses(monkeypatch):
    from app.services.jev_client import jev_client, JevResult, JevDecision

    async def dummy_classify(*args, **kwargs):
        return JevResult({
            "architectural_role": JevDecision({"choice": "core", "confidence": 0.9})
        })

    async def dummy_risk(*args, **kwargs):
        return JevResult({
            "semantic_risk": JevDecision({"score": 5}),
            "risk_category": JevDecision({"choice": "medium"})
        })

    async def dummy_test_file(*args, **kwargs):
        return JevResult({
            "is_test": JevDecision({"noul": 0.9}),
            "test_category": JevDecision({"choice": "unit-test"})
        })

    async def dummy_framework(*args, **kwargs):
        return JevResult({
            "framework": JevDecision({"choice": "react"}),
            "layer": JevDecision({"choice": "ui"})
        })

    async def dummy_dead_code(*args, **kwargs):
        return JevResult({
            "is_dead_code": JevDecision({"noul": 0.9}),
            "dead_code_category": JevDecision({"choice": "old"})
        })

    monkeypatch.setattr(jev_client, "classify_file", dummy_classify)
    monkeypatch.setattr(jev_client, "score_semantic_risk", dummy_risk)
    monkeypatch.setattr(jev_client, "detect_test_file", dummy_test_file)
    monkeypatch.setattr(jev_client, "detect_framework", dummy_framework)
    monkeypatch.setattr(jev_client, "detect_dead_code", dummy_dead_code)
    monkeypatch.setattr(jev_client, "detect_framework", dummy_framework)
    monkeypatch.setattr(jev_client, "detect_dead_code", dummy_dead_code)


def test_validate_repo_path_rejects_missing_path() -> None:
    with pytest.raises(UnsafeRepositoryPath):
        validate_repo_path("/definitely/not/a/real/repo")


@pytest.mark.asyncio
async def test_scan_repository_scores_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "allowed_repo_roots_raw", "")
    module = tmp_path / "service.py"
    module.write_text(
        """
import json

def load(value):
    if value:
        return json.loads(value)
    return {}
""",
        encoding="utf-8",
    )

    graph = await scan_repository(str(tmp_path))

    assert len(graph.files) == 1
    assert len(graph.symbols) == 1
    assert graph.files[0].load_bearing_score > 0


@pytest.mark.asyncio
async def test_scan_repository_resolves_nested_python_package_imports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "allowed_repo_roots_raw", "")
    package = tmp_path / "backend" / "app"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "scanner.py").write_text("def scan():\n    return True\n", encoding="utf-8")
    (package / "routes.py").write_text(
        "from app.scanner import scan\n\nresult = scan()\n", encoding="utf-8"
    )

    graph = await scan_repository(str(tmp_path))

    route_imports = [edge for edge in graph.imports if edge.source_path.endswith("routes.py")]
    assert route_imports
    assert route_imports[0].target == "app.scanner"
    assert route_imports[0].target_path == "backend/app/scanner.py"


@pytest.mark.asyncio
async def test_scan_repository_resolves_relative_typescript_imports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "allowed_repo_roots_raw", "")
    src = tmp_path / "frontend" / "src"
    src.mkdir(parents=True)
    (src / "api.ts").write_text("export const get = () => true;\n", encoding="utf-8")
    (src / "main.ts").write_text("import { get } from './api';\nget();\n", encoding="utf-8")

    graph = await scan_repository(str(tmp_path))

    imports = [edge for edge in graph.imports if edge.source_path.endswith("main.ts")]
    assert imports
    assert imports[0].target == "./api"
    assert imports[0].target_path == "frontend/src/api.ts"


@pytest.mark.asyncio
async def test_scan_repository_resolves_parent_directory_typescript_imports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "allowed_repo_roots_raw", "")
    src = tmp_path / "frontend" / "src"
    components = src / "components"
    app_dir = src / "app"
    components.mkdir(parents=True)
    app_dir.mkdir(parents=True)
    (components / "HeroSection.tsx").write_text(
        "export function HeroSection() { return null; }\n", encoding="utf-8"
    )
    (app_dir / "CartographerApp.tsx").write_text(
        "import { HeroSection } from '../components/HeroSection';\n",
        encoding="utf-8",
    )

    graph = await scan_repository(str(tmp_path))

    imports = [edge for edge in graph.imports if edge.source_path.endswith("CartographerApp.tsx")]
    assert imports
    assert imports[0].target == "../components/HeroSection"
    assert imports[0].target_path == "frontend/src/components/HeroSection.tsx"


@pytest.mark.asyncio
async def test_scan_repository_resolves_js_index_barrel_imports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "allowed_repo_roots_raw", "")
    src = tmp_path / "frontend" / "src"
    lib = src / "lib"
    lib.mkdir(parents=True)
    (lib / "index.ts").write_text("export const value = 1;\n", encoding="utf-8")
    (src / "main.ts").write_text("import { value } from './lib';\n", encoding="utf-8")

    graph = await scan_repository(str(tmp_path))

    imports = [edge for edge in graph.imports if edge.source_path.endswith("main.ts")]
    assert imports[0].target_path == "frontend/src/lib/index.ts"


@pytest.mark.asyncio
async def test_scan_repository_records_root_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "allowed_repo_roots_raw", "")
    (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")

    graph = await scan_repository(str(tmp_path))

    assert graph.root_path == str(tmp_path.resolve())


@pytest.mark.asyncio
async def test_scan_repository_reuses_unchanged_cached_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "allowed_repo_roots_raw", "")
    module = tmp_path / "service.py"
    module.write_text("def load():\n    return True\n", encoding="utf-8")
    first_graph = await scan_repository(str(tmp_path))
    previous = _cache_from_graph(first_graph)

    def fail_parse(*_args, **_kwargs):
        raise AssertionError("unchanged files should not be reparsed")

    monkeypatch.setattr("app.indexing.scanner.parse_python", fail_parse)
    second_graph = await scan_repository(str(tmp_path), previous_files=previous)

    assert len(second_graph.files) == 1
    assert second_graph.symbols[0].name == "load"


@pytest.mark.asyncio
async def test_scan_repository_reuses_same_hash_when_mtime_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "allowed_repo_roots_raw", "")
    module = tmp_path / "service.py"
    module.write_text("def load():\n    return True\n", encoding="utf-8")
    first_graph = await scan_repository(str(tmp_path))
    previous = _cache_from_graph(first_graph)
    stat = module.stat()
    os.utime(module, ns=(stat.st_atime_ns + 1_000_000_000, stat.st_mtime_ns + 1_000_000_000))

    def fail_parse(*_args, **_kwargs):
        raise AssertionError("same-hash files should not be reparsed")

    monkeypatch.setattr("app.indexing.scanner.parse_python", fail_parse)
    second_graph = await scan_repository(str(tmp_path), previous_files=previous)

    assert second_graph.files[0].mtime_ns == module.stat().st_mtime_ns
    assert second_graph.symbols[0].name == "load"


@pytest.mark.asyncio
async def test_scan_repository_rejects_repositories_over_file_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "allowed_repo_roots_raw", "")
    (tmp_path / "a.py").write_text("print('a')\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("print('b')\n", encoding="utf-8")

    with pytest.raises(RepositoryTooLarge):
        await scan_repository(str(tmp_path), max_files=1)


def _cache_from_graph(graph):
    return {
        file.path: CachedFile(
            file=file,
            symbols=[symbol for symbol in graph.symbols if symbol.file_path == file.path],
            imports=[edge for edge in graph.imports if edge.source_path == file.path],
        )
        for file in graph.files
    }
