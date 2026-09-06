from pathlib import Path

from app.indexing.js_parser import _configure_parser_language, parse_js_like


def test_parse_js_like_extracts_imports_classes_and_functions() -> None:
    source = """
import React from "react";
const answer = () => 42;
export function run(value) {
  if (value) return value;
}
class Runner {}
"""
    symbols, imports, complexity = parse_js_like(Path("app.ts"), "app.ts", source)

    assert {symbol.name for symbol in symbols} == {"answer", "run", "Runner"}
    assert imports[0].target == "react"
    assert complexity >= 2


def test_configure_parser_language_uses_modern_property_api() -> None:
    class ParserWithProperty:
        def __init__(self) -> None:
            self.language = None

    parser = ParserWithProperty()
    _configure_parser_language(parser, "typescript")

    assert parser.language == "typescript"


def test_configure_parser_language_supports_legacy_setter_api() -> None:
    class ParserWithSetter:
        def __init__(self) -> None:
            self.language_value = None

        def set_language(self, language) -> None:
            self.language_value = language

    parser = ParserWithSetter()
    _configure_parser_language(parser, "tsx")

    assert parser.language_value == "tsx"
