use pyo3::prelude::*;

#[pyclass(get_all)]
#[derive(Clone, Debug)]
pub struct IndexedFile {
    pub path: String,
    pub language: String,
    pub loc: usize,
    pub size_bytes: u64,
    pub mtime_ns: i64,
    pub content_hash: String,
    pub churn_count: i64,
    pub last_modified: Option<String>,
    pub complexity: usize,
    pub load_bearing_score: f64,
}

#[pyclass(get_all)]
#[derive(Clone, Debug)]
pub struct IndexedSymbol {
    pub id: String,
    pub file_path: String,
    pub name: String,
    pub kind: String,
    pub signature: Option<String>,
    pub start_line: usize,
    pub end_line: usize,
    pub complexity: usize,
}

#[pyclass(get_all)]
#[derive(Clone, Debug)]
pub struct IndexedImport {
    pub source_path: String,
    pub target: String,
    pub target_path: Option<String>,
    pub line_number: Option<usize>,
}

#[derive(Clone, Debug)]
pub struct CachedFileInput {
    pub path: String,
    pub file: IndexedFile,
    pub symbols: Vec<IndexedSymbol>,
    pub imports: Vec<IndexedImport>,
}

#[pyclass(get_all)]
#[derive(Clone, Debug, Default)]
pub struct ScanStats {
    pub git_churn_ms: f64,
    pub discovery_ms: f64,
    pub parse_hash_ms: f64,
    pub resolve_score_ms: f64,
    pub total_ms: f64,
    pub cached_stat_hits: usize,
    pub cached_hash_hits: usize,
    pub parsed_files: usize,
}

#[pyclass(get_all)]
#[derive(Clone, Debug)]
pub struct NativeRepoGraph {
    pub root_path: String,
    pub name: String,
    pub files: Vec<IndexedFile>,
    pub symbols: Vec<IndexedSymbol>,
    pub imports: Vec<IndexedImport>,
    pub stats: ScanStats,
}
