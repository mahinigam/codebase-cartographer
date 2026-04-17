from pathlib import Path

from app.indexing.js_parser import parse_js_like


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

