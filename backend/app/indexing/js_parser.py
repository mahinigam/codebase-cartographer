from __future__ import annotations

import logging
import re
from pathlib import Path

from app.models.graph import CodeSymbol, ImportEdge

try:
    from tree_sitter import Parser
    from tree_sitter_languages import get_language

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

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
    if TREE_SITTER_AVAILABLE:
        try:
            return _parse_with_tree_sitter(path, relative_path, source, language)
        except Exception as exc:
            logger.warning(
                f"Tree-sitter parse failed for {relative_path}; using regex fallback: {exc}"
            )
    return _parse_with_regex(relative_path, source)


def _parse_with_tree_sitter(
    path: Path, relative_path: str, source: str, language: str | None
) -> tuple[list[CodeSymbol], list[ImportEdge], int]:
    language_name = _language_name(path, language)
    parser = Parser()
    _configure_parser_language(parser, get_language(language_name))
    source_bytes = source.encode("utf-8", errors="ignore")
    tree = parser.parse(source_bytes)

    symbols: list[CodeSymbol] = []
    imports: list[ImportEdge] = []
    complexity = 1

    def text_for(node) -> str:
        return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")

    def walk(node) -> None:
        nonlocal complexity
        if node.type in COMPLEXITY_NODES:
            complexity += 1

        if node.type == "import_statement":
            source_node = node.child_by_field_name("source")
            if source_node:
                target = text_for(source_node).strip("'\"")
                imports.append(
                    ImportEdge(
                        source_path=relative_path,
                        target=target,
                        line_number=node.start_point[0] + 1,
                    )
                )
        elif node.type == "call_expression":
            function_node = node.child_by_field_name("function")
            arguments_node = node.child_by_field_name("arguments")
            if function_node and text_for(function_node) == "require" and arguments_node:
                for child in arguments_node.children:
                    if child.type == "string":
                        target = text_for(child).strip("'\"")
                        imports.append(
                            ImportEdge(
                                source_path=relative_path,
                                target=target,
                                line_number=node.start_point[0] + 1,
                            )
                        )
                        break
        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = text_for(name_node)
                symbols.append(_symbol(relative_path, name, "class", f"class {name}", node))
        elif node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = text_for(name_node)
                symbols.append(
                    _symbol(relative_path, name, "function", f"function {name}(...)", node)
                )
        elif node.type == "variable_declarator":
            name_node = node.child_by_field_name("name")
            value_node = node.child_by_field_name("value")
            if name_node and value_node and value_node.type in {"arrow_function", "function"}:
                name = text_for(name_node)
                symbols.append(
                    _symbol(relative_path, name, "function", f"const {name} = (...) =>", node)
                )

        for child in node.children:
            walk(child)

    walk(tree.root_node)
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
