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

A thin wrapper around the `git` CLI via `subprocess`. This avoids any C library dependency (no `libgit2`, no `pygit2`). Operations:

- `init`, `add`, `commit`, `tag`
- `log` (with time range and path filtering)
- `diff_names` (changed files between commits)
- `show` (file content at a commit)
- `show_commit` (single commit metadata)
- `rev_parse`, `list_files`

All errors are wrapped in `GitError`.

### `index.py` — SQLite Index

The sidecar index enables fast temporal queries without scanning Git history. Schema:

```sql
commits(hash, timestamp, author, message, metadata_json, is_checkpoint)
file_changes(commit_hash, path, change_type, old_hash, new_hash)
field_values(commit_hash, path, json_path, value_text, value_numeric)
```

Key properties:
- **Derived from Git** — rebuildable with `rebuild_index()`
- **Append-only** — new commits are indexed, never updated
- **Idempotent** — indexing the same commit twice is a no-op
- **Path-indexed** — all queries filter by path for performance

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

The spec mentions `pygit2` as a scaling strategy. The current implementation uses `subprocess` because:

1. **Zero dependencies** — no need to install `libgit2` C library
2. **Universal compatibility** — works on any system with git
3. **Simpler packaging** — no binary wheels, no platform-specific builds
4. **Good enough performance** — for the target workload (small artifacts, moderate commit rates)

A `pygit2` backend could be added as an optional optimization for high-volume use cases.
