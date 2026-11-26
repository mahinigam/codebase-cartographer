use crate::models::{IndexedFile, IndexedImport};
use rustc_hash::{FxHashMap, FxHashSet};
use std::path::Path;

const JS_SUFFIXES: &[&str] = &[".tsx", ".ts", ".jsx", ".js", ".mjs", ".cjs"];

fn add_module_aliases(modules: &mut FxHashMap<String, String>, module: &str, path: &str) {
    let parts: Vec<&str> = module.split('.').collect();
    for idx in 0..parts.len() {
        let alias = parts[idx..].join(".");
        modules.entry(alias).or_insert_with(|| path.to_string());
    }
}

fn python_module_index(file_paths: &FxHashSet<&str>) -> FxHashMap<String, String> {
    let mut sorted: Vec<&str> = file_paths.iter().copied().collect();
    sorted.sort_by(|a, b| a.len().cmp(&b.len()).then_with(|| a.cmp(b)));

    let mut modules = FxHashMap::default();
    for path in sorted {
        let Some(stem) = path.strip_suffix(".py") else {
            continue;
        };
        let module = stem.replace('/', ".");
        add_module_aliases(&mut modules, &module, path);
        if let Some(pkg) = module.strip_suffix(".__init__") {
            add_module_aliases(&mut modules, pkg, path);
        }
    }
    modules
}

fn js_module_index(file_paths: &FxHashSet<&str>) -> FxHashMap<String, String> {
    let mut sorted: Vec<&str> = file_paths.iter().copied().collect();
    sorted.sort_by(|a, b| a.len().cmp(&b.len()).then_with(|| a.cmp(b)));

    let mut modules = FxHashMap::default();
    for path in sorted {
        let Some((stem, _)) = path.rsplit_once('.') else {
            continue;
        };
        modules.entry(stem.to_string()).or_insert_with(|| path.to_string());
        modules
            .entry(format!("./{stem}"))
            .or_insert_with(|| path.to_string());
    }
    modules
}

fn normalize_posix_join(base_dir: &str, target: &str) -> Option<String> {
    let mut stack: Vec<&str> = if base_dir.is_empty() {
        Vec::new()
    } else {
        base_dir.split('/').filter(|s| !s.is_empty() && *s != ".").collect()
    };

    for part in target.split('/') {
        if part.is_empty() || part == "." {
            continue;
        }
        if part == ".." {
            if stack.is_empty() {
                return None;
            }
            stack.pop();
        } else {
            stack.push(part);
        }
    }

    Some(stack.join("/"))
}

fn lookup_js_module(normalized: &str, modules: &FxHashMap<String, String>) -> Option<String> {
    let mut stems = Vec::with_capacity(2);
    stems.push(normalized);
    for suffix in JS_SUFFIXES {
        if let Some(stripped) = normalized.strip_suffix(suffix) {
            stems.push(stripped);
            break;
        }
    }
    for stem in stems {
        if let Some(resolved) = modules.get(stem) {
            return Some(resolved.clone());
        }
        let index_candidate = format!("{stem}/index");
        if let Some(resolved) = modules.get(&index_candidate) {
            return Some(resolved.clone());
        }
    }
    None
}

fn resolve_relative_module(
    source_path: &str,
    target: &str,
    modules: &FxHashMap<String, String>,
) -> Option<String> {
    let parent = match source_path.rsplit_once('/') {
        Some((p, _)) => p,
        None => "",
    };
    let normalized = normalize_posix_join(parent, target)?;
    lookup_js_module(&normalized, modules)
}

fn resolve_relative_python_module(
    source_path: &str,
    target: &str,
    modules: &FxHashMap<String, String>,
) -> Option<String> {
    let leading_dots = target.bytes().take_while(|&b| b == b'.').count();
    let module_tail = &target[leading_dots..];

    let without_ext = match Path::new(source_path).with_extension("").to_str() {
        Some(s) => s.to_string(),
        None => source_path.to_string(),
    };
    let source_parts: Vec<&str> = without_ext.split('/').filter(|s| !s.is_empty()).collect();
    let keep = source_parts.len().saturating_sub(leading_dots);
    let mut parts: Vec<&str> = source_parts[..keep].to_vec();
    if !module_tail.is_empty() {
        parts.push(module_tail);
    }
    let candidate = parts.join(".").trim_matches('.').to_string();
    modules.get(&candidate).cloned()
}

pub fn resolve_imports(files: &[IndexedFile], imports: &mut [IndexedImport]) {
    let file_paths: FxHashSet<&str> = files.iter().map(|f| f.path.as_str()).collect();
    let python_modules = python_module_index(&file_paths);
    let js_modules = js_module_index(&file_paths);

    for edge in imports.iter_mut() {
        if edge.target.starts_with("./") || edge.target.starts_with("../") {
            edge.target_path = resolve_relative_module(&edge.source_path, &edge.target, &js_modules);
        } else if edge.target.starts_with('.') {
            edge.target_path =
                resolve_relative_python_module(&edge.source_path, &edge.target, &python_modules);
        } else if let Some(resolved) = python_modules.get(&edge.target) {
            edge.target_path = Some(resolved.clone());
        } else if let Some(resolved) = js_modules.get(&edge.target) {
            edge.target_path = Some(resolved.clone());
        }
    }
}

pub fn score_load_bearing_files(files: &mut [IndexedFile], imports: &[IndexedImport]) {
    let mut fan_in: FxHashMap<&str, usize> = FxHashMap::default();
    let mut fan_out: FxHashMap<&str, usize> = FxHashMap::default();

    for edge in imports {
        *fan_out.entry(edge.source_path.as_str()).or_insert(0) += 1;
        if let Some(ref target_path) = edge.target_path {
            *fan_in.entry(target_path.as_str()).or_insert(0) += 1;
        }
    }

    let max_complexity = files
        .iter()
        .map(|f| f.complexity)
        .max()
        .unwrap_or(1)
        .max(1) as f64;
    let max_churn = files
        .iter()
        .map(|f| f.churn_count)
        .max()
        .unwrap_or(1)
        .max(1) as f64;
    let max_fan_in = fan_in.values().copied().max().unwrap_or(1).max(1) as f64;

    for file in files.iter_mut() {
        let mut fan_in_score = (*fan_in.get(file.path.as_str()).unwrap_or(&0) as f64) / max_fan_in;
        if file.loc < 30 && file.complexity <= 1 {
            fan_in_score *= 0.3;
        }
        let f_out = *fan_out.get(file.path.as_str()).unwrap_or(&0) as f64;
        let raw = 100.0
            * (0.45 * fan_in_score
                + 0.25 * (file.complexity as f64 / max_complexity)
                + 0.2 * (file.churn_count as f64 / max_churn)
                + 0.1 * (f_out / 10.0).min(1.0));
        file.load_bearing_score = (raw * 100.0).round() / 100.0;
    }
}
