from pathlib import Path

from app.indexing.python_parser import parse_python


def test_parse_python_extracts_symbols_and_imports() -> None:
    source = """
import os
from app.core import config

class Cartographer:
    def map(self, repo):
        if repo:
            return repo
        return None
"""
    symbols, imports, complexity = parse_python(Path("example.py"), "example.py", source)

    names = {symbol.name for symbol in symbols}
    targets = {edge.target for edge in imports}

    assert {"Cartographer", "map"} <= names
    assert {"os", "app.core"} <= targets
    assert complexity >= 2

