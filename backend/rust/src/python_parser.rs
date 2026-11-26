use crate::models::{IndexedImport, IndexedSymbol};
use tree_sitter::{Node, Parser};

fn is_branch_node(kind: &str) -> bool {
    matches!(
        kind,
        "if_statement"
            | "elif_clause"
            | "for_statement"
            | "while_statement"
            | "try_statement"
            | "except_clause"
            | "boolean_operator"
            | "conditional_expression"
            | "match_statement"
    )
}

fn subtree_complexity(node: Node<'_>) -> usize {
    let mut count = 1usize;
    let mut stack = vec![node];
    while let Some(curr) = stack.pop() {
        if is_branch_node(curr.kind()) {
            count += 1;
        }
        let mut cursor = curr.walk();
        for child in curr.children(&mut cursor) {
            stack.push(child);
        }
    }
    count
}

fn node_text<'a>(node: Node<'_>, source: &'a [u8]) -> &'a str {
    node.utf8_text(source).unwrap_or("")
}

fn extract_param_names(params_node: Node<'_>, source: &[u8]) -> String {
    let mut names = Vec::new();
    let mut cursor = params_node.walk();
    for child in params_node.children(&mut cursor) {
        match child.kind() {
            "identifier" => {
                let text = node_text(child, source);
                if !text.is_empty() {
                    names.push(text.to_string());
                }
            }
            "typed_parameter" | "default_parameter" | "typed_default_parameter" => {
                let mut inner_cursor = child.walk();
                for sub in child.children(&mut inner_cursor) {
                    if sub.kind() == "identifier" {
                        let text = node_text(sub, source);
                        if !text.is_empty() {
                            names.push(text.to_string());
                        }
                        break;
                    }
                }
            }
            _ => {}
        }
    }
    names.join(", ")
}

fn has_syntax_error(node: Node<'_>) -> bool {
    let mut stack = vec![node];
    while let Some(curr) = stack.pop() {
        if curr.is_error() || curr.is_missing() {
            return true;
        }
        if matches!(curr.kind(), "function_definition" | "class_definition") {
            let empty_body = curr
                .child_by_field_name("body")
                .is_none_or(|b| b.start_byte() == b.end_byte());
            if empty_body {
                return true;
            }
        }
        let mut cursor = curr.walk();
        for child in curr.children(&mut cursor) {
            stack.push(child);
        }
    }
    false
}

pub fn parse_python(
    relative_path: &str,
    source: &str,
    parser: &mut Parser,
) -> (Vec<IndexedSymbol>, Vec<IndexedImport>, usize) {
    let language: tree_sitter::Language = tree_sitter_python::LANGUAGE.into();
    if parser.set_language(&language).is_err() {
        return (Vec::new(), Vec::new(), 0);
    }
    let source_bytes = source.as_bytes();
    let Some(tree) = parser.parse(source_bytes, None) else {
        return (Vec::new(), Vec::new(), 0);
    };
    let root = tree.root_node();
    if root.has_error() || has_syntax_error(root) {
        return (Vec::new(), Vec::new(), 0);
    }

    let mut symbols = Vec::new();
    let mut imports = Vec::new();
    let mut total_complexity = 1usize;

    let mut stack = vec![root];
    while let Some(node) = stack.pop() {
        let kind = node.kind();
        if is_branch_node(kind) {
            total_complexity += 1;
        }

        match kind {
            "class_definition" => {
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
                        complexity: subtree_complexity(node),
                    });
                }
            }
            "function_definition" => {
                if let Some(name_node) = node.child_by_field_name("name") {
                    let name = node_text(name_node, source_bytes).to_string();
                    let is_async = node
                        .child(0)
                        .is_some_and(|c| c.kind() == "async" || node_text(c, source_bytes) == "async");
                    let prefix = if is_async { "async def" } else { "def" };
                    let args = node
                        .child_by_field_name("parameters")
                        .map(|p| extract_param_names(p, source_bytes))
                        .unwrap_or_default();
                    let start_line = node.start_position().row + 1;
                    let end_line = node.end_position().row + 1;
                    symbols.push(IndexedSymbol {
                        id: format!("{relative_path}:{name}:{start_line}"),
                        file_path: relative_path.to_string(),
                        name: name.clone(),
                        kind: "function".to_string(),
                        signature: Some(format!("{prefix} {name}({args})")),
                        start_line,
                        end_line,
                        complexity: subtree_complexity(node),
                    });
                }
            }
            "import_statement" => {
                let line_number = node.start_position().row + 1;
                let mut cursor = node.walk();
                for child in node.children_by_field_name("name", &mut cursor) {
                    let target = match child.kind() {
                        "aliased_import" => child
                            .child_by_field_name("name")
                            .map(|n| node_text(n, source_bytes))
                            .unwrap_or(""),
                        _ => node_text(child, source_bytes),
                    };
                    if !target.is_empty() {
                        imports.push(IndexedImport {
                            source_path: relative_path.to_string(),
                            target: target.to_string(),
                            target_path: None,
                            line_number: Some(line_number),
                        });
                    }
                }
            }
            "import_from_statement" => {
                let line_number = node.start_position().row + 1;
                if let Some(mod_node) = node.child_by_field_name("module_name") {
                    let target = node_text(mod_node, source_bytes).trim().to_string();
                    if !target.is_empty() {
                        imports.push(IndexedImport {
                            source_path: relative_path.to_string(),
                            target,
                            target_path: None,
                            line_number: Some(line_number),
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

    (symbols, imports, total_complexity)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extracts_async_typed_functions_classes_imports_and_complexity() {
        let src = r#"
import os, sys as s
from ..core.config import Settings

class Engine:
    async def run(self, x: int, y: str = "a"):
        if x > 0 and y:
            for i in range(x):
                pass
        elif x < 0:
            return -1
        return 0
"#;
        let mut parser = Parser::new();
        let (syms, imps, comp) = parse_python("pkg/eng.py", src, &mut parser);
        assert_eq!(syms.len(), 2);
        assert_eq!(syms[0].kind, "class");
        assert_eq!(syms[0].signature.as_deref(), Some("class Engine"));
        assert_eq!(syms[1].kind, "function");
        assert_eq!(syms[1].signature.as_deref(), Some("async def run(self, x, y)"));
        assert!(comp >= 5);
        let targets: Vec<&str> = imps.iter().map(|i| i.target.as_str()).collect();
        assert_eq!(targets, vec!["os", "sys", "..core.config"]);
    }

    #[test]
    fn syntax_error_or_truncated_def_returns_empty() {
        let mut parser = Parser::new();
        assert_eq!(parse_python("bad.py", "def run():", &mut parser).0.len(), 0);
        assert_eq!(parse_python("bad.py", "class Broken(", &mut parser).0.len(), 0);
    }
}
