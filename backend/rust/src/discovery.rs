use ignore::WalkBuilder;
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};

pub const IGNORED_DIRS: &[&str] = &[
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".next",
    ".turbo",
    "coverage",
];

#[derive(Clone, Debug)]
pub struct DiscoveredFile {
    pub abs_path: PathBuf,
    pub rel_path: String,
    pub language: &'static str,
}

pub fn language_for_path(path: &Path) -> Option<&'static str> {
    let ext = path.extension()?.to_str()?;
    match ext {
        "py" => Some("python"),
        "js" | "jsx" => Some("javascript"),
        "ts" | "tsx" => Some("typescript"),
        _ => None,
    }
}

fn is_ignored_dir_name(name: &str) -> bool {
    IGNORED_DIRS.contains(&name)
}

fn escapes_root(path: &Path, root_canonical: &Path) -> bool {
    let Ok(meta) = fs::symlink_metadata(path) else {
        return true;
    };
    if !meta.file_type().is_symlink() {
        return false;
    }
    match fs::canonicalize(path) {
        Ok(resolved) => !resolved.starts_with(root_canonical),
        Err(_) => true,
    }
}

pub fn discover_source_files(root: &Path) -> Vec<DiscoveredFile> {
    let Ok(root_canonical) = fs::canonicalize(root) else {
        return Vec::new();
    };

    let mut files = Vec::new();
    let walker = WalkBuilder::new(root)
        .hidden(false)
        .git_ignore(false)
        .git_global(false)
        .git_exclude(false)
        .ignore(false)
        .parents(false)
        .follow_links(false)
        .filter_entry(|entry| {
            if entry.depth() == 0 {
                return true;
            }
            if entry.file_type().is_some_and(|ft| ft.is_dir()) {
                if let Some(name) = entry.file_name().to_str() {
                    return !is_ignored_dir_name(name);
                }
            }
            true
        })
        .build();

    for entry in walker.flatten() {
        if entry.depth() == 0 {
            continue;
        }
        let path = entry.path();
        // Check if any component is in IGNORED_DIRS (mirrors discovery.py)
        if path.components().any(|c| {
            c.as_os_str()
                .to_str()
                .is_some_and(is_ignored_dir_name)
        }) {
            continue;
        }
        // Check is_file (follows symlinks for files, matching Path.is_file())
        if !path.is_file() {
            continue;
        }
        let Some(language) = language_for_path(path) else {
            continue;
        };
        if escapes_root(path, &root_canonical) {
            continue;
        }
        let Ok(rel) = path.strip_prefix(root) else {
            continue;
        };
        let rel_posix = rel
            .components()
            .map(|c| c.as_os_str().to_string_lossy())
            .collect::<Vec<_>>()
            .join("/");
        files.push(DiscoveredFile {
            abs_path: path.to_path_buf(),
            rel_path: rel_posix,
            language,
        });
    }

    files.sort_by(|a, b| a.rel_path.cmp(&b.rel_path));
    files
}

pub fn safe_snippet(root: &Path, relative: &str, limit: usize) -> String {
    let Ok(repo_root) = fs::canonicalize(root) else {
        return String::new();
    };
    let candidate = root.join(relative);
    let Ok(resolved) = fs::canonicalize(&candidate) else {
        return String::new();
    };
    if !resolved.starts_with(&repo_root) || !resolved.is_file() {
        return String::new();
    }
    let Ok(mut file) = fs::File::open(&resolved) else {
        return String::new();
    };
    // Read enough bytes to cover `limit` UTF-8 chars (worst case 4 bytes/char)
    let max_bytes = limit.saturating_mul(4);
    let mut buf = Vec::with_capacity(max_bytes.min(65536));
    if (&mut file).take(max_bytes as u64).read_to_end(&mut buf).is_err() {
        return String::new();
    }
    let text = String::from_utf8_lossy(&buf);
    text.chars().take(limit).collect()
}
