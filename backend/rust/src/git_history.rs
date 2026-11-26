use chrono::{DateTime, FixedOffset};
use git2::{DiffOptions, Repository, Sort};
use rustc_hash::FxHashMap;
use std::path::Path;

#[derive(Clone, Debug)]
pub struct ChurnEntry {
    pub count: i64,
    pub last_modified: String,
}

fn format_git_time(time: git2::Time) -> String {
    let secs = time.seconds();
    let offset_secs = time.offset_minutes() * 60;
    let offset = FixedOffset::east_opt(offset_secs)
        .unwrap_or_else(|| FixedOffset::east_opt(0).unwrap());
    DateTime::from_timestamp(secs, 0)
        .map(|dt| dt.with_timezone(&offset).to_rfc3339())
        .unwrap_or_default()
}

pub fn file_churn(root: &Path) -> FxHashMap<String, ChurnEntry> {
    let mut churn: FxHashMap<String, ChurnEntry> = FxHashMap::default();
    let Ok(repo) = Repository::discover(root) else {
        return churn;
    };

    let Ok(mut revwalk) = repo.revwalk() else {
        return churn;
    };
    if revwalk.push_head().is_err() {
        return churn;
    }
    let _ = revwalk.set_sorting(Sort::TIME);

    let mut diff_opts = DiffOptions::new();
    diff_opts.include_unmodified(false);

    for oid_res in revwalk.take(500) {
        let Ok(oid) = oid_res else {
            continue;
        };
        let Ok(commit) = repo.find_commit(oid) else {
            continue;
        };
        let timestamp = format_git_time(commit.time());
        let Ok(tree) = commit.tree() else {
            continue;
        };
        let parent_tree = commit.parent(0).ok().and_then(|p| p.tree().ok());
        let Ok(diff) = repo.diff_tree_to_tree(parent_tree.as_ref(), Some(&tree), Some(&mut diff_opts)) else {
            continue;
        };

        for delta in diff.deltas() {
            let path_opt = delta.new_file().path().or_else(|| delta.old_file().path());
            let Some(path) = path_opt else {
                continue;
            };
            let key = path.to_string_lossy().replace('\\', "/");
            let entry = churn.entry(key).or_insert_with(|| ChurnEntry {
                count: 0,
                last_modified: timestamp.clone(),
            });
            entry.count += 1;
            if entry.last_modified < timestamp {
                entry.last_modified = timestamp.clone();
            }
        }
    }

    churn
}
