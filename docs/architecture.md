# Architecture

Technical overview of GitLedger's internals.

---

## Design Principles

1. **Git is the source of truth.** The index is derived and rebuildable.
2. **Zero dependencies.** Only Python stdlib and the git CLI.
3. **Synchronous writes, queryable index.** Commits are synchronous; the index enables fast queries.
4. **Structured artifacts.** GitLedger is optimized for small JSON files, not binary blobs.
5. **Deterministic replay.** Any historical state can be reconstructed from Git.

---

## Module Overview

```
gitledger/
├── repo.py        # Public API — the Repo class
├── git.py         # Git CLI wrapper (subprocess)
├── index.py       # SQLite sidecar index
├── diff.py        # Semantic diff engine
├── trend.py       # Trend extraction + anomaly detection
├── narrative.py   # Narrative summary generation
├── models.py      # Data models (frozen dataclasses)
└── __init__.py    # Public exports
```

### `repo.py` — The Public API

The `Repo` class is the only entry point users need. It composes the git layer, index, and analysis modules into a clean interface. All 13 query/write methods are here.

### `git.py` — Git Operations

A high-performance wrapper around the `git` CLI via `subprocess`. This avoids any C library dependency (no `libgit2`, no `pygit2`). Operations:

- `init`, `add`, `commit`, `tag`
- `log` (with time range, path filtering, and `--grep` for pushing search into git)
- `diff_names` (changed files between commits)
- `show` / `show_many` (file content at a commit, batched)
- `show_commit` (single commit metadata)
- `rev_parse`, `list_files`
- `snapshot_contents` (all files at a commit in one batch)

All errors are wrapped in `GitError`.

### `index.py` — SQLite Index

The sidecar index enables fast temporal queries without scanning Git history. Schema:

```sql
commits(hash, timestamp, author, message, metadata_json, is_checkpoint)
file_changes(commit_hash, path, change_type)
field_values(commit_hash, path, json_path, value_text, value_numeric)
```

Key properties:
- **Derived from Git** — rebuildable with `rebuild_index()`
- **Append-only** — new commits are indexed, never updated
- **Idempotent** — indexing the same commit twice is a no-op
- **Path-indexed** — all queries filter by path for performance

Strategic indexes:
- `idx_file_changes_path` — speeds up path-based timeline queries
- `idx_field_values_json_path` — composite index on `(path, json_path)` for trend lookups
- `idx_commits_timestamp` — enables fast temporal filtering

JSON flattening converts nested structures into `(json_path, value)` pairs:
```
{"config": {"retry": 3}} → [("config.retry", 3)]
{"items": [1, 2]}        → [("items[0]", 1), ("items[1]", 2)]
```

### `diff.py` — Semantic Diffs

Compares two JSON documents recursively, producing per-field change entries. Handles:
- Added, removed, and modified fields
- Nested objects (dot-path notation)
- Arrays (index notation)
- Type changes
- Non-JSON files (raw text diff)

### `trend.py` — Trend Extraction

Converts indexed field values into `TrendPoint` series and runs z-score anomaly detection with configurable sigma thresholds.

### `narrative.py` — Narrative Generation

Produces human-readable summaries from commit lists and file changes. Extracts:
- Commit counts and time ranges
- Most active files
- Contributors
- Event type frequencies
- Checkpoint counts

### `models.py` — Data Models

All models are frozen `@dataclass` with `__slots__` for immutability and memory efficiency:
- `Commit`, `FileChange`, `FieldValue`
- `DiffEntry`, `TrendPoint`, `Episode`, `Anomaly`
- `ChangeType` enum

---

## Performance

### Two Speed Lanes

Queries take one of two paths depending on whether they need file content or just metadata:

**Fast Lane — SQLite Index**

Metadata-only queries via SQLite index. Some methods use `git log` or `--grep` for filtering, but never read file content.

- `timeline()`, `trend()`, `anomalies()`, `episodes()`
- `most_changed()`, `correlate()`, `search()`, `narrate()`

**Content Lane — `cat-file --batch`**

Reads file content through a persistent git process. Batched for throughput.

- `diff()`, `snapshot()`, `drift()`

### The Persistent Reader

Instead of spawning a new subprocess for every file read, GitLedger keeps a single `git cat-file --batch` process alive. Objects are streamed through its stdin/stdout pipe — one request per line, no process creation overhead.

- `show()` — 1 object per call
- `show_many()` — N objects batched, chunked at 200 to avoid pipe buffer deadlocks
- `snapshot_contents()` — all files at a commit in one batch (replaces N+1 `show()` calls)

The reader auto-restarts if the underlying process dies (e.g., repo GC, broken pipe).

### Batched Operations

Several `Repo` methods leverage batched reads to minimize subprocess overhead:

- **`diff()`** uses `show_many` to fetch two file versions in one round-trip
- **`drift()`** reads all historical versions of a file in one batch
- **`snapshot()`** uses `list_files` + `show_many` (1 subprocess + 1 cat-file batch)
- **`search()`** pushes message filtering into git via `--grep` (single subprocess), then cross-references with the SQLite index for path filtering

---

## Data Flow

```
                     ┌──────────┐
                     │  Agent   │
                     └────┬─────┘
                          │
                     write artifacts
                          │
                          ▼
                     ┌──────────┐
                     │   Git    │  ← immutable, causal, content-addressed
                     └────┬─────┘
                          │
                    commit event
                          │
                          ▼
                   ┌────────────┐
                   │  Indexer   │  ← flattens JSON, extracts fields
                   └──────┬─────┘
                          │
                          ▼
                ┌───────────────┐
                │  SQLite Index │  ← .gitledger/index.db
                └───────┬───────┘
                        │
                   query API
                        │
                        ▼
              ┌──────────────────┐
              │  Repo.timeline() │
              │  Repo.diff()     │
              │  Repo.trend()    │
              │  Repo.anomalies()│
              │  ...             │
              └──────────────────┘
```

---

## Commit Strategy

### Event Commits

Message format: `event:{entity}:{event_type}`

Body: structured JSON metadata.

```
event:agent-alpha:beliefs_updated

{
  "agent_id": "agent-alpha",
  "event_type": "beliefs_updated",
  "timestamp": "2026-03-08T14:23:00+00:00",
  "changed_paths": ["agents/agent-alpha/beliefs.json"],
  "checkpoint": false
}
```

### Checkpoint Commits

Message format: `checkpoint:{YYYYMMDDTHHMMSS}`

Tagged as `checkpoint-{YYYYMMDDTHHMMSS}`.

Checkpoints allow efficient timeline traversal and serve as stable reference points.

---

## Why Subprocess Instead of pygit2?

GitLedger uses `subprocess` to call git instead of `pygit2` because:

1. **Zero dependencies** — no need to install `libgit2` C library
2. **Universal compatibility** — works on any system with git
3. **Simpler packaging** — no binary wheels, no platform-specific builds
4. **Persistent `cat-file --batch`** process eliminates per-read subprocess overhead
5. **Batched reads** (chunked at 200) avoid pipe buffer deadlocks while maximizing throughput

The performance characteristics are well-suited for the target workload: small structured artifacts with moderate commit rates.
