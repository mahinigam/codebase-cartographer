from __future__ import annotations

import logging
import re
from pathlib import Path

from app._native import parse_js_like_native
from app.models.graph import CodeSymbol, ImportEdge

Parser = object  # Kept for test monkeypatch compatibility.

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

logger = logging.getLogger(__name__)

COMPLEXITY_NODES = {
    "if_statement",
    "for_statement",
    "for_in_statement",
    "for_of_statement",
    "while_statement",
    "do_statement",
    "switch_statement",
    "catch_clause",
    "conditional_expression",
    "logical_expression",
}


def parse_js_like(
    path: Path, relative_path: str, source: str, language: str | None = None
) -> tuple[list[CodeSymbol], list[ImportEdge], int]:
    raw_symbols, raw_imports, complexity = parse_js_like_native(
        str(path), relative_path, source, language
    )
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


def _configure_parser_language(parser, tree_sitter_language) -> None:
    if hasattr(parser, "language"):
        parser.language = tree_sitter_language
    else:
        parser.set_language(tree_sitter_language)


def _language_name(path: Path, language: str | None) -> str:
    if path.suffix == ".tsx":
        return "tsx"
    if language == "typescript":
        return "typescript"
    return "javascript"


def _parse_with_regex(
    relative_path: str, source: str
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


def _symbol(
    relative_path: str, name: str, kind: str, signature: str, node_or_line
) -> CodeSymbol:
    if hasattr(node_or_line, "start_point"):
        start_line = node_or_line.start_point[0] + 1
        end_line = node_or_line.end_point[0] + 1
    else:
        start_line = int(node_or_line)
        end_line = int(node_or_line)
    return CodeSymbol(
        id=f"{relative_path}:{name}:{start_line}",
        file_path=relative_path,
        name=name,
        kind=kind,
        signature=signature,
        start_line=start_line,
        end_line=end_line,
    )
