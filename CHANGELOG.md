# Changelog

All notable changes to GitLedger are documented here.

This project follows [Semantic Versioning](https://semver.org/).

---

## [1.0.0] — 2026-03-08

### Added

- **Core API** — `Repo` class with 13 query/write methods:
  - `timeline()` — commit history for a path
  - `diff()` — semantic field-level diffs between commits
  - `trend()` — numeric field trend extraction
  - `episodes()` — group related commits by path pattern and event type
  - `snapshot()` — all file contents at a commit
  - `drift()` — detect field value changes across history
  - `narrate()` — human-readable narrative summaries
  - `anomalies()` — z-score anomaly detection on numeric trends
  - `search()` — search commit messages with optional path filtering
  - `correlate()` — find commits that changed multiple paths together
  - `most_changed()` — most frequently modified paths
  - `write()` — write JSON or text artifacts
  - `commit_event()` — create structured event commits
  - `commit_checkpoint()` — create tagged checkpoint commits

- **SQLite sidecar index** at `.gitledger/index.db`
  - Derived from Git history, fully rebuildable
  - Indexed by path and timestamp for fast queries
  - JSON flattening for field-level value tracking
  - `sync()` and `rebuild_index()` for index management

- **Semantic diff engine**
  - Field-level JSON comparison (nested objects, arrays, type changes)
  - Dot-path notation for nested fields (`config.retry`)
  - Index notation for arrays (`items[2]`)
  - Fallback to raw text diff for non-JSON files

- **Trend analysis**
  - Numeric field extraction across commit history
  - Z-score anomaly detection with configurable sigma threshold

- **Narrative generation**
  - Commit counts, time ranges, most active files
  - Contributor summaries, event type frequencies, checkpoint counts

- **Data models**
  - Frozen dataclasses with `__slots__`: `Commit`, `FileChange`, `DiffEntry`, `TrendPoint`, `Episode`, `Anomaly`, `FieldValue`
  - `ChangeType` enum: `ADDED`, `MODIFIED`, `DELETED`, `RENAMED`

- **Git layer**
  - Subprocess-based git operations (zero C dependencies)
  - `Repo.init()` for creating new repositories
  - Context manager support

- **CI/CD**
  - GitHub Actions CI with Python 3.10-3.13 test matrix
  - Automated PyPI publishing via trusted publishing on tag push

- **Documentation**
  - API reference, user guide, architecture docs
  - Examples for common use cases
  - README with quick start guide

### Design Decisions

- **subprocess over pygit2** — zero dependencies, universal compatibility
- **SQLite over custom index** — battle-tested, zero config, rebuildable
- **frozen dataclasses** — immutable by default, memory efficient
- **no external dependencies** — only Python stdlib + git CLI
