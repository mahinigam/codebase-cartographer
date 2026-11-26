use crate::models::{IndexedImport, IndexedSymbol};
use std::path::Path;
use tree_sitter::{Language, Node, Parser};

fn is_complexity_node(node: Node<'_>, source: &[u8]) -> bool {
    match node.kind() {
        "if_statement"
        | "for_statement"
        | "for_in_statement"
        | "for_of_statement"
        | "while_statement"
        | "do_statement"
        | "switch_statement"
        | "catch_clause"
        | "conditional_expression"
        | "ternary_expression"
        | "logical_expression" => true,
        "binary_expression" => node
            .child_by_field_name("operator")
            .is_some_and(|op| matches!(node_text(op, source), "&&" | "||" | "??")),
        _ => false,
    }
}

fn node_text<'a>(node: Node<'_>, source: &'a [u8]) -> &'a str {
    node.utf8_text(source).unwrap_or("")
}

fn select_language(path: &Path, language_hint: Option<&str>) -> Language {
    if path.extension().and_then(|e| e.to_str()) == Some("tsx") {
        return tree_sitter_typescript::LANGUAGE_TSX.into();
    }
    if language_hint == Some("typescript")
        || path.extension().and_then(|e| e.to_str()) == Some("ts")
    {
        return tree_sitter_typescript::LANGUAGE_TYPESCRIPT.into();
    }
    tree_sitter_javascript::LANGUAGE.into()
}

pub fn parse_js_like(
    path: &Path,
    relative_path: &str,
    source: &str,
    language_hint: Option<&str>,
    parser: &mut Parser,
) -> (Vec<IndexedSymbol>, Vec<IndexedImport>, usize) {
    let ts_lang = select_language(path, language_hint);
    if parser.set_language(&ts_lang).is_err() {
        return (Vec::new(), Vec::new(), 1);
    }

    let source_bytes = source.as_bytes();
    let Some(tree) = parser.parse(source_bytes, None) else {
        return (Vec::new(), Vec::new(), 1);
    };

    let mut symbols = Vec::new();
    let mut imports = Vec::new();
    let mut complexity = 1usize;

    let mut stack = vec![tree.root_node()];
    while let Some(node) = stack.pop() {
        let kind = node.kind();
        if is_complexity_node(node, source_bytes) {
            complexity += 1;
        }

        match kind {
            "import_statement" => {
                if let Some(source_node) = node.child_by_field_name("source") {
                    let target = node_text(source_node, source_bytes)
                        .trim_matches(|c| c == '\'' || c == '"')
                        .to_string();
                    if !target.is_empty() {
                        imports.push(IndexedImport {
                            source_path: relative_path.to_string(),
                            target,
                            target_path: None,
                            line_number: Some(node.start_position().row + 1),
                        });
                    }
                }
            }
            "call_expression" => {
                let func_node = node.child_by_field_name("function");
                let args_node = node.child_by_field_name("arguments");
                if let (Some(fn_n), Some(args_n)) = (func_node, args_node) {
                    if node_text(fn_n, source_bytes) == "require" {
                        let mut cursor = args_n.walk();
                        for child in args_n.children(&mut cursor) {
                            if child.kind() == "string" {
                                let target = node_text(child, source_bytes)
                                    .trim_matches(|c| c == '\'' || c == '"')
                                    .to_string();
                                if !target.is_empty() {
                                    imports.push(IndexedImport {
                                        source_path: relative_path.to_string(),
                                        target,
                                        target_path: None,
                                        line_number: Some(node.start_position().row + 1),
                                    });
                                }
                                break;
                            }
                        }
                    }
                }
            }
            "class_declaration" => {
                if let Some(name_node) = node.child_by_field_name("name") {
                    let name = node_text(name_node, source_bytes).to_string();
                    let start_line = node.start_position().row + 1;
                    let end_line = node.end_position().row + 1;
                    symbols.push(IndexedSymbol {
                        id: format!("{relative_path}:{name}:{start_line}"),
                        file_path: relative_path.to_string(),
                        name: name.clone(),
                        kind: "class".to_string(),
                        signature: Some(format!("class {name}")),
                        start_line,
                        end_line,
                        complexity: 0,
                    });
                }
            }
            "function_declaration" => {
                if let Some(name_node) = node.child_by_field_name("name") {
                    let name = node_text(name_node, source_bytes).to_string();
                    let start_line = node.start_position().row + 1;
                    let end_line = node.end_position().row + 1;
                    symbols.push(IndexedSymbol {
                        id: format!("{relative_path}:{name}:{start_line}"),
                        file_path: relative_path.to_string(),
                        name: name.clone(),
                        kind: "function".to_string(),
                        signature: Some(format!("function {name}(...)")),
                        start_line,
                        end_line,
                        complexity: 0,
                    });
                }
            }
            "variable_declarator" => {
                if let (Some(name_node), Some(val_node)) = (
                    node.child_by_field_name("name"),
                    node.child_by_field_name("value"),
                ) {
                    if matches!(val_node.kind(), "arrow_function" | "function" | "function_expression")
                    {
                        let name = node_text(name_node, source_bytes).to_string();
                        let start_line = node.start_position().row + 1;
                        let end_line = node.end_position().row + 1;
                        symbols.push(IndexedSymbol {
                            id: format!("{relative_path}:{name}:{start_line}"),
                            file_path: relative_path.to_string(),
                            name: name.clone(),
                            kind: "function".to_string(),
                            signature: Some(format!("const {name} = (...) =>")),
                            start_line,
                            end_line,
                            complexity: 0,
                        });
                    }
                }
            }
            _ => {}
        }

        let mut cursor = node.walk();
        let children: Vec<Node<'_>> = node.children(&mut cursor).collect();
        for child in children.into_iter().rev() {
            stack.push(child);
        }
    }

    (symbols, imports, complexity)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_tsx_jsx_arrows_classes_and_require() {
        let src = r#"
import React from 'react';
const fs = require("fs");
export class Widget {}
export function render(ok: boolean) {
  return ok ? <div>hi</div> : null;
}
const helper = async () => {
  if (true && false) { return 1; }
  return 0;
};
"#;
        let mut parser = Parser::new();
        let (syms, imps, comp) =
            parse_js_like(Path::new("Widget.tsx"), "Widget.tsx", src, Some("typescript"), &mut parser);
        let names: Vec<&str> = syms.iter().map(|s| s.name.as_str()).collect();
        assert_eq!(names, vec!["Widget", "render", "helper"]);
        let targets: Vec<&str> = imps.iter().map(|i| i.target.as_str()).collect();
        assert_eq!(targets, vec!["react", "fs"]);
        assert!(comp >= 4);
    }
}
