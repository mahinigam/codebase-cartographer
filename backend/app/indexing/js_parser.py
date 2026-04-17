import re
from pathlib import Path

from app.models.graph import CodeSymbol, ImportEdge

IMPORT_RE = re.compile(
    r"^\s*import(?:.|\n)*?from\s+['\"]([^'\"]+)['\"]"
    r"|^\s*import\s+['\"]([^'\"]+)['\"]"
)
REQUIRE_RE = re.compile(r"require\(['\"]([^'\"]+)['\"]\)")
FUNCTION_RE = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)"
)
ARROW_RE = re.compile(
    r"^\s*(?:export\s+)?(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>"
)
CLASS_RE = re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)")


def parse_js_like(
    path: Path, relative_path: str, source: str
) -> tuple[list[CodeSymbol], list[ImportEdge], int]:
    symbols: list[CodeSymbol] = []
    imports: list[ImportEdge] = []
    lines = source.splitlines()
    for line_no, line in enumerate(lines, start=1):
        import_match = IMPORT_RE.search(line) or REQUIRE_RE.search(line)
        if import_match:
            target = next(group for group in import_match.groups() if group)
            imports.append(
                ImportEdge(source_path=relative_path, target=target, line_number=line_no)
            )

        class_match = CLASS_RE.search(line)
        if class_match:
            name = class_match.group(1)
            symbols.append(_symbol(relative_path, name, "class", f"class {name}", line_no))
            continue

        function_match = FUNCTION_RE.search(line)
        if function_match:
            name = function_match.group(1)
            args = function_match.group(2).strip()
            symbols.append(
                _symbol(relative_path, name, "function", f"function {name}({args})", line_no)
            )
            continue

        arrow_match = ARROW_RE.search(line)
        if arrow_match:
            name = arrow_match.group(1)
            symbols.append(
                _symbol(relative_path, name, "function", f"const {name} = (...) =>", line_no)
            )

    complexity = 1 + len(re.findall(r"\b(if|for|while|catch|case|\?\s*)\b|&&|\|\|", source))
    return symbols, imports, complexity


def _symbol(relative_path: str, name: str, kind: str, signature: str, line_no: int) -> CodeSymbol:
    return CodeSymbol(
        id=f"{relative_path}:{name}:{line_no}",
        file_path=relative_path,
        name=name,
        kind=kind,
        signature=signature,
        start_line=line_no,
        end_line=line_no,
    )
