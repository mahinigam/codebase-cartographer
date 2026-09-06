from pathlib import Path

import pytest

from app.core.config import settings
from app.indexing.scanner import UnsafeRepositoryPath, scan_repository, validate_repo_path


def test_validate_repo_path_rejects_missing_path() -> None:
    with pytest.raises(UnsafeRepositoryPath):
        validate_repo_path("/definitely/not/a/real/repo")


def test_scan_repository_scores_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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

    graph = scan_repository(str(tmp_path))

    assert len(graph.files) == 1
    assert len(graph.symbols) == 1
    assert graph.files[0].load_bearing_score > 0


def test_scan_repository_resolves_nested_python_package_imports(
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

    graph = scan_repository(str(tmp_path))

    route_imports = [edge for edge in graph.imports if edge.source_path.endswith("routes.py")]
    assert route_imports
    assert route_imports[0].target == "app.scanner"
    assert route_imports[0].target_path == "backend/app/scanner.py"


def test_scan_repository_resolves_relative_typescript_imports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "allowed_repo_roots_raw", "")
    src = tmp_path / "frontend" / "src"
    src.mkdir(parents=True)
    (src / "api.ts").write_text("export const get = () => true;\n", encoding="utf-8")
    (src / "main.ts").write_text("import { get } from './api';\nget();\n", encoding="utf-8")

    graph = scan_repository(str(tmp_path))

    imports = [edge for edge in graph.imports if edge.source_path.endswith("main.ts")]
    assert imports
    assert imports[0].target == "./api"
    assert imports[0].target_path == "frontend/src/api.ts"


def test_scan_repository_resolves_parent_directory_typescript_imports(
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

    graph = scan_repository(str(tmp_path))

    imports = [edge for edge in graph.imports if edge.source_path.endswith("CartographerApp.tsx")]
    assert imports
    assert imports[0].target == "../components/HeroSection"
    assert imports[0].target_path == "frontend/src/components/HeroSection.tsx"


def test_scan_repository_resolves_js_index_barrel_imports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "allowed_repo_roots_raw", "")
    src = tmp_path / "frontend" / "src"
    lib = src / "lib"
    lib.mkdir(parents=True)
    (lib / "index.ts").write_text("export const value = 1;\n", encoding="utf-8")
    (src / "main.ts").write_text("import { value } from './lib';\n", encoding="utf-8")

    graph = scan_repository(str(tmp_path))

    imports = [edge for edge in graph.imports if edge.source_path.endswith("main.ts")]
    assert imports[0].target_path == "frontend/src/lib/index.ts"


def test_scan_repository_records_root_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "allowed_repo_roots_raw", "")
    (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")

    graph = scan_repository(str(tmp_path))

    assert graph.root_path == str(tmp_path.resolve())
