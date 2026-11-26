use crate::discovery::{discover_source_files, DiscoveredFile};
use crate::git_history::{file_churn, ChurnEntry};
use crate::js_parser::parse_js_like;
use crate::models::{
    CachedFileInput, IndexedFile, IndexedImport, IndexedSymbol, NativeRepoGraph, ScanStats,
};
use crate::python_parser::parse_python;
use crate::resolver::{resolve_imports, score_load_bearing_files};
use rayon::prelude::*;
use rustc_hash::FxHashMap;
use sha2::{Digest, Sha256};
use std::cell::RefCell;
use std::fs;
use std::io::Read;
use std::path::Path;
use std::time::{Instant, UNIX_EPOCH};
use thiserror::Error;
use tree_sitter::Parser;

#[derive(Error, Debug)]
pub enum ScanError {
    #[error("Repository has {found} supported source files; limit is {limit}.")]
    RepositoryTooLarge { found: usize, limit: usize },
}

enum FileResult {
    StatCacheHit {
        file: IndexedFile,
        symbols: Vec<IndexedSymbol>,
        imports: Vec<IndexedImport>,
    },
    HashCacheHit {
        file: IndexedFile,
        symbols: Vec<IndexedSymbol>,
        imports: Vec<IndexedImport>,
    },
    Parsed {
        file: IndexedFile,
        symbols: Vec<IndexedSymbol>,
        imports: Vec<IndexedImport>,
    },
}

fn read_source_head(path: &Path, max_bytes: usize) -> String {
    if max_bytes == 0 {
        let bytes = fs::read(path).unwrap_or_default();
        return String::from_utf8_lossy(&bytes).into_owned();
    }
    let Ok(mut f) = fs::File::open(path) else {
        return String::new();
    };
    let mut buf = Vec::with_capacity(max_bytes.min(65536));
    let _ = (&mut f).take(max_bytes as u64).read_to_end(&mut buf);
    String::from_utf8_lossy(&buf).into_owned()
}

fn content_hash(source: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(source.as_bytes());
    let digest = hasher.finalize();
    let mut hex = String::with_capacity(64);
    for byte in digest {
        use std::fmt::Write;
        let _ = write!(&mut hex, "{byte:02x}");
    }
    hex
}

fn mtime_ns(meta: &fs::Metadata) -> i64 {
    meta.modified()
        .ok()
        .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
        .map(|d| d.as_nanos() as i64)
        .unwrap_or(0)
}

fn process_one_file(
    item: &DiscoveredFile,
    cached: Option<&CachedFileInput>,
    churn_entry: Option<&ChurnEntry>,
    max_file_bytes: usize,
    parser: &mut Parser,
) -> FileResult {
    let meta = fs::metadata(&item.abs_path).ok();
    let size_bytes = meta.as_ref().map(|m| m.len()).unwrap_or(0);
    let mtime = meta.as_ref().map(mtime_ns).unwrap_or(0);

    if let Some(c) = cached {
        if !c.file.content_hash.is_empty()
            && c.file.size_bytes == size_bytes
            && c.file.mtime_ns == mtime
        {
            let mut f = c.file.clone();
            f.size_bytes = size_bytes;
            f.mtime_ns = mtime;
            if let Some(h) = churn_entry {
                f.churn_count = h.count;
                f.last_modified = Some(h.last_modified.clone());
            }
            return FileResult::StatCacheHit {
                file: f,
                symbols: c.symbols.clone(),
                imports: c.imports.clone(),
            };
        }
    }

    let source = read_source_head(&item.abs_path, max_file_bytes);
    let hash = content_hash(&source);

    if let Some(c) = cached {
        if c.file.content_hash == hash {
            let mut f = c.file.clone();
            f.size_bytes = size_bytes;
            f.mtime_ns = mtime;
            f.content_hash = hash;
            if let Some(h) = churn_entry {
                f.churn_count = h.count;
                f.last_modified = Some(h.last_modified.clone());
            }
            return FileResult::HashCacheHit {
                file: f,
                symbols: c.symbols.clone(),
                imports: c.imports.clone(),
            };
        }
    }

    let loc = source.lines().filter(|l| !l.trim().is_empty()).count();
    let (symbols, imports, complexity) = match item.language {
        "python" => parse_python(&item.rel_path, &source, parser),
        "javascript" | "typescript" => {
            parse_js_like(&item.abs_path, &item.rel_path, &source, Some(item.language), parser)
        }
        _ => (Vec::new(), Vec::new(), 0),
    };

    let (churn_count, last_modified) = match churn_entry {
        Some(h) => (h.count, Some(h.last_modified.clone())),
        None => (0, None),
    };

    FileResult::Parsed {
        file: IndexedFile {
            path: item.rel_path.clone(),
            language: item.language.to_string(),
            loc,
            size_bytes,
            mtime_ns: mtime,
            content_hash: hash,
            churn_count,
            last_modified,
            complexity,
            load_bearing_score: 0.0,
        },
        symbols,
        imports,
    }
}

pub fn scan_repo(
    root: &Path,
    previous_files: &FxHashMap<String, CachedFileInput>,
    max_files: usize,
    max_file_bytes: usize,
) -> Result<NativeRepoGraph, ScanError> {
    let t0 = Instant::now();
    let churn = file_churn(root);
    let t1 = Instant::now();

    let discovered = discover_source_files(root);
    if max_files > 0 && discovered.len() > max_files {
        return Err(ScanError::RepositoryTooLarge {
            found: discovered.len(),
            limit: max_files,
        });
    }
    let t2 = Instant::now();

    thread_local! {
        static TL_PARSER: RefCell<Parser> = RefCell::new(Parser::new());
    }

    let results: Vec<FileResult> = discovered
        .par_iter()
        .map(|item| {
            TL_PARSER.with(|cell| {
                let mut parser = cell.borrow_mut();
                let cached = previous_files.get(&item.rel_path);
                let churn_entry = churn.get(&item.rel_path);
                process_one_file(item, cached, churn_entry, max_file_bytes, &mut parser)
            })
        })
        .collect();
    let t3 = Instant::now();

    let mut files = Vec::with_capacity(results.len());
    let mut symbols = Vec::new();
    let mut imports = Vec::new();
    let mut stats = ScanStats {
        git_churn_ms: (t1 - t0).as_secs_f64() * 1000.0,
        discovery_ms: (t2 - t1).as_secs_f64() * 1000.0,
        parse_hash_ms: (t3 - t2).as_secs_f64() * 1000.0,
        ..Default::default()
    };

    for res in results {
        match res {
            FileResult::StatCacheHit {
                file,
                symbols: s,
                imports: i,
            } => {
                stats.cached_stat_hits += 1;
                files.push(file);
                symbols.extend(s);
                imports.extend(i);
            }
            FileResult::HashCacheHit {
                file,
                symbols: s,
                imports: i,
            } => {
                stats.cached_hash_hits += 1;
                files.push(file);
                symbols.extend(s);
                imports.extend(i);
            }
            FileResult::Parsed {
                file,
                symbols: s,
                imports: i,
            } => {
                stats.parsed_files += 1;
                files.push(file);
                symbols.extend(s);
                imports.extend(i);
            }
        }
    }

    let t4 = Instant::now();
    resolve_imports(&files, &mut imports);
    score_load_bearing_files(&mut files, &imports);
    let t5 = Instant::now();

    stats.resolve_score_ms = (t5 - t4).as_secs_f64() * 1000.0;
    stats.total_ms = (t5 - t0).as_secs_f64() * 1000.0;

    let root_str = root.to_string_lossy().into_owned();
    let name = root
        .file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or_default();

    Ok(NativeRepoGraph {
        root_path: root_str,
        name,
        files,
        symbols,
        imports,
        stats,
    })
}
