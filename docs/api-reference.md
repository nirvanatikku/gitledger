# API Reference

Complete reference for the GitLedger Python API.

---

## `gitledger.Repo`

The primary interface. All operations go through a `Repo` instance.

### Constructor

```python
Repo(path: str | Path)
```

Open an existing GitLedger repository.

**Parameters:**
- `path` — Path to a Git repository.

**Raises:**
- `GitError` — If the path is not a valid Git repository.

---

### Class Methods

#### `Repo.init(path)`

```python
Repo.init(path: str | Path) -> Repo
```

Initialize a new Git repository and return a `Repo` instance. Creates the directory if it doesn't exist. Configures a default git user for commits.

**Parameters:**
- `path` — Directory to initialize.

**Returns:** A new `Repo` instance.

---

### Context Manager

`Repo` supports the context manager protocol. The index database connection is closed on exit.

```python
with Repo("./memory") as repo:
    timeline = repo.timeline("agents/alpha/state.json")
```

---

## Write Operations

### `repo.write(path, content)`

```python
repo.write(path: str, content: str | dict | list) -> None
```

Write an artifact to the repository working tree and stage it. Does **not** create a commit — call `commit_event()` or `commit_checkpoint()` after writing.

**Parameters:**
- `path` — Relative file path within the repository.
- `content` — A string, dict, or list. Dicts and lists are serialized to JSON with 2-space indent.

**Example:**
```python
repo.write("agents/alpha/state.json", {
    "confidence_score": 0.85,
    "status": "active",
})
```

---

### `repo.commit_event(entity, event_type, ...)`

```python
repo.commit_event(
    entity: str,
    event_type: str,
    changed_paths: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str
```

Create an event commit with structured metadata in the commit body.

**Commit message format:** `event:{entity}:{event_type}`

**Commit body:** JSON with `agent_id`, `event_type`, `timestamp`, `changed_paths`, and any additional metadata.

**Parameters:**
- `entity` — The entity identifier (e.g., `"agent-alpha"`).
- `event_type` — The type of event (e.g., `"beliefs_updated"`).
- `changed_paths` — List of changed file paths (informational).
- `metadata` — Additional key-value pairs merged into the commit body.

**Returns:** The commit hash (40-character hex string).

**Example:**
```python
hash = repo.commit_event(
    "agent-alpha",
    "beliefs_updated",
    changed_paths=["agents/alpha/beliefs.json"],
    metadata={"trigger": "observation"},
)
```

---

### `repo.commit_checkpoint(tag=None)`

```python
repo.commit_checkpoint(tag: str | None = None) -> str
```

Create a checkpoint commit with an annotated tag. Checkpoints are stable reference points for efficient timeline traversal.

**Parameters:**
- `tag` — Custom tag name. Defaults to `checkpoint-{YYYYMMDDTHHMMSS}`.

**Returns:** The commit hash.

---

## Query Operations

### `repo.timeline(path, since=None, until=None)`

```python
repo.timeline(
    path: str,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[Commit]
```

Return the commit timeline for a specific file path, ordered chronologically.

**Parameters:**
- `path` — Exact file path to query.
- `since` — Only include commits after this time.
- `until` — Only include commits before this time.

**Returns:** List of `Commit` objects.

**Example:**
```python
from datetime import datetime, timedelta, timezone

recent = repo.timeline(
    "agents/alpha/state.json",
    since=datetime.now(tz=timezone.utc) - timedelta(hours=24),
)
```

---

### `repo.diff(path, commit_a, commit_b)`

```python
repo.diff(
    path: str,
    commit_a: str,
    commit_b: str,
) -> list[DiffEntry]
```

Compute a semantic, field-level diff for a path between two commits. For JSON files, this produces per-field change entries rather than line-level diffs.

**Parameters:**
- `path` — File path to diff.
- `commit_a` — Starting commit hash.
- `commit_b` — Ending commit hash.

**Returns:** List of `DiffEntry` objects.

**Example:**
```python
timeline = repo.timeline("agents/alpha/state.json")
diffs = repo.diff("agents/alpha/state.json",
    commit_a=timeline[0].hash,
    commit_b=timeline[-1].hash)

for d in diffs:
    print(f"{d.field}: {d.old_value} -> {d.new_value}")
```

---

### `repo.trend(path, field, since=None, until=None)`

```python
repo.trend(
    path: str,
    field: str,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[TrendPoint]
```

Extract trend data for a numeric JSON field across commits.

**Parameters:**
- `path` — File path containing the field.
- `field` — JSON field name (top-level key or dot-path like `"config.retry"`).
- `since` / `until` — Time range filter.

**Returns:** List of `TrendPoint` objects, each with `commit_hash`, `timestamp`, and `value`.

**Example:**
```python
trend = repo.trend("agents/alpha/state.json", "confidence_score")
for point in trend:
    print(f"{point.timestamp}: {point.value}")
```

---

### `repo.episodes(path_pattern, event_type=None, ...)`

```python
repo.episodes(
    path_pattern: str,
    event_type: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    window: timedelta | None = None,
) -> list[Episode]
```

Group related commits into episodes by path pattern and optionally filter by event type.

**Parameters:**
- `path_pattern` — Glob-style pattern (e.g., `"agents/alpha/*"`).
- `event_type` — Filter commits whose message contains this substring.
- `window` — If set and `since` is not provided, computes `since = now - window`.

**Returns:** List of `Episode` objects.

---

### `repo.snapshot(commit=None)`

```python
repo.snapshot(commit: str | None = None) -> dict[str, str]
```

Return all file contents at a given commit.

**Parameters:**
- `commit` — Commit hash or ref. Defaults to `"HEAD"`.

**Returns:** Dict mapping file path to file content.

**Example:**
```python
snap = repo.snapshot()
state = json.loads(snap["agents/alpha/state.json"])
```

---

### `repo.drift(path, schema=None)`

```python
repo.drift(
    path: str,
    schema: dict[str, type] | None = None,
) -> list[FieldValue]
```

Detect field value changes for a structured artifact across its timeline. Returns a `FieldValue` for each field that changed between consecutive commits.

**Parameters:**
- `path` — File path to analyze.
- `schema` — Optional dict of `{field_name: type}`. If provided, only these fields are tracked.

**Returns:** List of `FieldValue` objects.

---

### `repo.narrate(path_pattern="*", since=None, until=None)`

```python
repo.narrate(
    path_pattern: str = "*",
    since: datetime | None = None,
    until: datetime | None = None,
) -> str
```

Generate a human-readable narrative summary of repository activity.

**Returns:** A multi-line string describing commit count, most active files, contributors, checkpoints, and event types.

**Example:**
```python
print(repo.narrate(path_pattern="agents/*"))
```

Output:
```
Between 2026-03-08 10:00 and 2026-03-08 14:00, 5 commits were recorded.

Most active files:
  - agents/alpha/state.json (3 changes)
  - agents/alpha/beliefs.json (1 change)

Event types:
  - state_updated (3)
  - beliefs_updated (1)
```

---

### `repo.anomalies(path, field, sigma=2.0, ...)`

```python
repo.anomalies(
    path: str,
    field: str,
    sigma: float = 2.0,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[Anomaly]
```

Detect anomalies in a numeric field's trend using z-score analysis.

**Parameters:**
- `path` — File path.
- `field` — Numeric JSON field name.
- `sigma` — Z-score threshold (default 2.0). Lower values are more sensitive.

**Returns:** List of `Anomaly` objects with `commit_hash`, `value`, `expected_range`, and `severity`.

---

### `repo.search(query, paths=None)`

```python
repo.search(
    query: str,
    paths: list[str] | None = None,
) -> list[Commit]
```

Search commit messages for a query string. Case-insensitive.

**Parameters:**
- `query` — Substring to search for.
- `paths` — Optional glob patterns to restrict results to commits that touched matching files.

**Returns:** List of matching `Commit` objects.

---

### `repo.correlate(path_a, path_b, ...)`

```python
repo.correlate(
    path_a: str,
    path_b: str,
    since: datetime | None = None,
    until: datetime | None = None,
    window: timedelta | None = None,
) -> list[Commit]
```

Find commits that changed both paths. Useful for detecting co-evolving artifacts.

**Parameters:**
- `path_a` / `path_b` — Two file paths.
- `window` — If set and `since` is not provided, computes `since = now - window`.

**Returns:** List of `Commit` objects that touched both paths.

---

### `repo.most_changed(pattern=None, limit=10)`

```python
repo.most_changed(
    pattern: str | None = None,
    limit: int = 10,
) -> list[tuple[str, int]]
```

Return the most frequently changed paths.

**Parameters:**
- `pattern` — Optional glob-style filter.
- `limit` — Max number of results.

**Returns:** List of `(path, change_count)` tuples, descending by frequency.

---

## Index Management

### `repo.sync()`

```python
repo.sync() -> int
```

Index all un-indexed commits. The index is a SQLite sidecar database derived entirely from Git history. Call this after external commits or to catch up after pulling.

**Returns:** Number of newly indexed commits.

---

### `repo.rebuild_index()`

```python
repo.rebuild_index() -> int
```

Drop and rebuild the entire index from scratch.

**Returns:** Total number of indexed commits.

---

### `repo.close()`

```python
repo.close() -> None
```

Close the index database connection.

---

## Data Models

All models are frozen dataclasses with `__slots__` for memory efficiency.

### `Commit`

```python
@dataclass(frozen=True, slots=True)
class Commit:
    hash: str
    timestamp: datetime
    message: str
    author: str
    metadata: dict[str, Any]
    is_checkpoint: bool
```

### `FileChange`

```python
@dataclass(frozen=True, slots=True)
class FileChange:
    commit_hash: str
    path: str
    change_type: ChangeType  # ADDED, MODIFIED, DELETED, RENAMED
    old_hash: str | None
    new_hash: str | None
```

### `DiffEntry`

```python
@dataclass(frozen=True, slots=True)
class DiffEntry:
    path: str
    field: str          # JSON field path, e.g. "config.retry"
    old_value: Any
    new_value: Any
```

### `TrendPoint`

```python
@dataclass(frozen=True, slots=True)
class TrendPoint:
    commit_hash: str
    timestamp: datetime
    value: float
```

### `Episode`

```python
@dataclass(frozen=True, slots=True)
class Episode:
    id: str
    start_commit: str
    end_commit: str
    path_pattern: str
    episode_type: str
    commits: list[str]
```

### `Anomaly`

```python
@dataclass(frozen=True, slots=True)
class Anomaly:
    commit_hash: str
    timestamp: datetime
    path: str
    field: str
    value: float
    expected_range: tuple[float, float]
    severity: float     # z-score
```

### `FieldValue`

```python
@dataclass(frozen=True, slots=True)
class FieldValue:
    commit_hash: str
    path: str
    json_path: str
    value: Any
```

### `ChangeType`

```python
class ChangeType(enum.Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
```

---

## Exceptions

### `GitError`

Raised when a git operation fails. Wraps the stderr output from the git CLI.

```python
from gitledger.git import GitError

try:
    repo = Repo("/nonexistent")
except GitError as e:
    print(f"Git error: {e}")
```
