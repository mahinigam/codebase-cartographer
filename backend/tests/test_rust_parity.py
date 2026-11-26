from pathlib import Path

from app._native import parse_python_native, scan_repo_native

from app.models.graph import CachedFile, CodeFile, CodeSymbol, ImportEdge


def test_parse_python_native_returns_empty_on_truncated_syntax() -> None:
    symbols, imports, complexity = parse_python_native("huge.py", "def run():")
    assert symbols == []
    assert imports == []
    assert complexity == 0


def test_scan_repo_native_incremental_stat_cache(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("import os\ndef greet():\n    return 'hi'\n", encoding="utf-8")
    (tmp_path / "b.ts").write_text("import './a';\nexport const x = () => 1;\n", encoding="utf-8")

    cold = scan_repo_native(str(tmp_path), None, 0, 2_000_000)
    assert cold.stats.parsed_files == 2
    assert cold.stats.cached_stat_hits == 0

    previous = {
        f.path: CachedFile(
            file=CodeFile(
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
            ),
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
                for s in cold.symbols
                if s.file_path == f.path
            ],
            imports=[
                ImportEdge(
                    source_path=i.source_path,
                    target=i.target,
                    target_path=i.target_path,
                    line_number=i.line_number,
                )
                for i in cold.imports
                if i.source_path == f.path
            ],
        )
        for f in cold.files
    }

    warm = scan_repo_native(str(tmp_path), previous, 0, 2_000_000)
    assert warm.stats.parsed_files == 0
    assert warm.stats.cached_stat_hits == 2
