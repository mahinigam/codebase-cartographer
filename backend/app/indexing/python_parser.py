from pathlib import Path

from app._native import parse_python_native
from app.models.graph import CodeSymbol, ImportEdge


def parse_python(
    path: Path, relative_path: str, source: str
) -> tuple[list[CodeSymbol], list[ImportEdge], int]:
    _ = path
    raw_symbols, raw_imports, complexity = parse_python_native(relative_path, source)
    symbols = [
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
        for s in raw_symbols
    ]
    imports = [
        ImportEdge(
            source_path=i.source_path,
            target=i.target,
            target_path=i.target_path,
            line_number=i.line_number,
        )
        for i in raw_imports
    ]
    return symbols, imports, complexity
