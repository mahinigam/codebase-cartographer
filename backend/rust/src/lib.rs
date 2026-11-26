pub mod discovery;
pub mod git_history;
pub mod js_parser;
pub mod models;
pub mod python_parser;
pub mod resolver;
pub mod scanner;

use models::{
    CachedFileInput, IndexedFile, IndexedImport, IndexedSymbol, NativeRepoGraph, ScanStats,
};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use rustc_hash::FxHashMap;
use std::path::Path;
use tree_sitter::Parser;

pyo3::create_exception!(app._native, RepositoryTooLargeError, PyValueError);

#[pyfunction]
#[pyo3(signature = (root_path, previous_files=None, max_files=0, max_file_bytes=2_000_000))]
fn scan_repo_native(
    py: Python<'_>,
    root_path: String,
    previous_files: Option<&Bound<'_, pyo3::types::PyDict>>,
    max_files: usize,
    max_file_bytes: usize,
) -> PyResult<NativeRepoGraph> {
    let mut cache_map: FxHashMap<String, CachedFileInput> = FxHashMap::default();
    if let Some(dict) = previous_files {
        for (k, v) in dict.iter() {
            let key: String = k.extract()?;
            let file_obj = v.getattr("file")?;
            let path_val: String = file_obj.getattr("path")?.extract()?;
            let language: String = file_obj.getattr("language")?.extract()?;
            let loc: usize = file_obj.getattr("loc")?.extract()?;
            let size_bytes: u64 = file_obj.getattr("size_bytes")?.extract()?;
            let mtime_ns: i64 = file_obj.getattr("mtime_ns")?.extract()?;
            let content_hash: String = file_obj
                .getattr("content_hash")?
                .extract::<Option<String>>()?
                .unwrap_or_default();
            let churn_count: i64 = file_obj.getattr("churn_count")?.extract()?;
            let last_modified: Option<String> = file_obj.getattr("last_modified")?.extract()?;
            let complexity: usize = file_obj.getattr("complexity")?.extract()?;
            let load_bearing_score: f64 = file_obj.getattr("load_bearing_score")?.extract()?;

            let syms_py = v.getattr("symbols")?;
            let mut symbols = Vec::new();
            for s in syms_py.try_iter()? {
                let s = s?;
                symbols.push(IndexedSymbol {
                    id: s.getattr("id")?.extract()?,
                    file_path: s.getattr("file_path")?.extract()?,
                    name: s.getattr("name")?.extract()?,
                    kind: s.getattr("kind")?.extract()?,
                    signature: s.getattr("signature")?.extract()?,
                    start_line: s.getattr("start_line")?.extract()?,
                    end_line: s.getattr("end_line")?.extract()?,
                    complexity: s.getattr("complexity")?.extract()?,
                });
            }

            let imps_py = v.getattr("imports")?;
            let mut imports = Vec::new();
            for i in imps_py.try_iter()? {
                let i = i?;
                imports.push(IndexedImport {
                    source_path: i.getattr("source_path")?.extract()?,
                    target: i.getattr("target")?.extract()?,
                    target_path: i.getattr("target_path")?.extract()?,
                    line_number: i.getattr("line_number")?.extract()?,
                });
            }

            cache_map.insert(
                key,
                CachedFileInput {
                    path: path_val.clone(),
                    file: IndexedFile {
                        path: path_val,
                        language,
                        loc,
                        size_bytes,
                        mtime_ns,
                        content_hash,
                        churn_count,
                        last_modified,
                        complexity,
                        load_bearing_score,
                    },
                    symbols,
                    imports,
                },
            );
        }
    }

    let result = py.allow_threads(move || {
        scanner::scan_repo(Path::new(&root_path), &cache_map, max_files, max_file_bytes)
    });

    match result {
        Ok(graph) => Ok(graph),
        Err(scanner::ScanError::RepositoryTooLarge { found, limit }) => {
            Err(RepositoryTooLargeError::new_err(format!(
                "Repository has {found} supported source files; limit is {limit}."
            )))
        }
    }
}

#[pyfunction]
fn discover_source_files_native(py: Python<'_>, root_path: String) -> Vec<String> {
    py.allow_threads(move || {
        discovery::discover_source_files(Path::new(&root_path))
            .into_iter()
            .map(|d| d.abs_path.to_string_lossy().into_owned())
            .collect()
    })
}

#[pyfunction]
fn safe_snippet_native(
    py: Python<'_>,
    root_path: String,
    relative: String,
    limit: usize,
) -> String {
    py.allow_threads(move || discovery::safe_snippet(Path::new(&root_path), &relative, limit))
}

#[pyfunction]
fn parse_python_native(
    py: Python<'_>,
    relative_path: String,
    source: String,
) -> (Vec<IndexedSymbol>, Vec<IndexedImport>, usize) {
    py.allow_threads(move || {
        let mut parser = Parser::new();
        python_parser::parse_python(&relative_path, &source, &mut parser)
    })
}

#[pyfunction]
#[pyo3(signature = (path, relative_path, source, language=None))]
fn parse_js_like_native(
    py: Python<'_>,
    path: String,
    relative_path: String,
    source: String,
    language: Option<String>,
) -> (Vec<IndexedSymbol>, Vec<IndexedImport>, usize) {
    py.allow_threads(move || {
        let mut parser = Parser::new();
        js_parser::parse_js_like(
            Path::new(&path),
            &relative_path,
            &source,
            language.as_deref(),
            &mut parser,
        )
    })
}

#[pymodule]
fn _native(py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<IndexedFile>()?;
    m.add_class::<IndexedSymbol>()?;
    m.add_class::<IndexedImport>()?;
    m.add_class::<ScanStats>()?;
    m.add_class::<NativeRepoGraph>()?;
    m.add("RepositoryTooLargeError", py.get_type::<RepositoryTooLargeError>())?;
    m.add_function(wrap_pyfunction!(scan_repo_native, m)?)?;
    m.add_function(wrap_pyfunction!(discover_source_files_native, m)?)?;
    m.add_function(wrap_pyfunction!(safe_snippet_native, m)?)?;
    m.add_function(wrap_pyfunction!(parse_python_native, m)?)?;
    m.add_function(wrap_pyfunction!(parse_js_like_native, m)?)?;
    Ok(())
}
