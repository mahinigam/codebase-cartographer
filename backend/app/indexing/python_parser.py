import ast
from pathlib import Path

from app.models.graph import CodeSymbol, ImportEdge


def parse_python(
    path: Path, relative_path: str, source: str
) -> tuple[list[CodeSymbol], list[ImportEdge], int]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], [], 0

    symbols: list[CodeSymbol] = []
    imports: list[ImportEdge] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            symbols.append(
                CodeSymbol(
                    id=f"{relative_path}:{node.name}:{node.lineno}",
                    file_path=relative_path,
                    name=node.name,
                    kind="class",
                    signature=f"class {node.name}",
                    start_line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    complexity=_complexity(node),
                )
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = ", ".join(arg.arg for arg in node.args.args)
            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            symbols.append(
                CodeSymbol(
                    id=f"{relative_path}:{node.name}:{node.lineno}",
                    file_path=relative_path,
                    name=node.name,
                    kind="function",
                    signature=f"{prefix} {node.name}({args})",
                    start_line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    complexity=_complexity(node),
                )
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    ImportEdge(
                        source_path=relative_path,
                        target=alias.name,
                        line_number=node.lineno,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            imports.append(
                ImportEdge(source_path=relative_path, target=module, line_number=node.lineno)
            )

    return symbols, imports, _complexity(tree)


def _complexity(node: ast.AST) -> int:
    branch_nodes = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.Try,
        ast.ExceptHandler,
        ast.BoolOp,
        ast.IfExp,
        ast.Match,
    )
    return 1 + sum(1 for child in ast.walk(node) if isinstance(child, branch_nodes))
