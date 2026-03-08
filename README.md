# GitLedger

**Structural memory for agents and automation.**

GitLedger is a Python library that turns a Git repository into a deterministic temporal memory substrate. It provides temporal queries, semantic diffs, trend extraction, anomaly detection, and narrative summaries over repository history.

**Zero dependencies.** Only Python 3.10+ and git on PATH.

## Install

```bash
pip install gitledger
```

## Quick Start

```python
from gitledger import Repo

repo = Repo.init("./memory")

# Write structured artifacts
repo.write("agents/alpha/state.json", {
    "confidence_score": 0.85,
    "status": "active",
})

# Create an event commit
repo.commit_event("agent-alpha", "state_initialized",
    changed_paths=["agents/alpha/state.json"])

# Update state
repo.write("agents/alpha/state.json", {
    "confidence_score": 0.72,
    "status": "degraded",
})
repo.commit_event("agent-alpha", "state_updated",
    changed_paths=["agents/alpha/state.json"])

# Query the timeline
timeline = repo.timeline("agents/alpha/state.json")

# Semantic diffs — field-level, not line-level
diffs = repo.diff("agents/alpha/state.json",
    commit_a=timeline[0].hash,
    commit_b=timeline[-1].hash)

for d in diffs:
    print(f"{d.field}: {d.old_value} -> {d.new_value}")
# confidence_score: 0.85 -> 0.72
# status: active -> degraded
```

## Core API

| Method | Description |
|---|---|
| `timeline(path, since, until)` | Commit history for a path |
| `diff(path, commit_a, commit_b)` | Semantic field-level diffs |
| `trend(path, field, since, until)` | Numeric field trends |
| `episodes(pattern, event_type, window)` | Group related commits |
| `snapshot(commit)` | All file contents at a commit |
| `drift(path, schema)` | Detect field value changes |
| `narrate(pattern, since, until)` | Human-readable narrative |
| `anomalies(path, field, sigma)` | Statistical outlier detection |
| `search(query, paths)` | Search commit messages |
| `correlate(path_a, path_b, window)` | Find co-changing paths |
| `most_changed(pattern, limit)` | Most frequently modified paths |

| Write Method | Description |
|---|---|
| `write(path, content)` | Write a JSON or text artifact |
| `commit_event(entity, event_type)` | Create an event commit |
| `commit_checkpoint(tag)` | Create a checkpoint with tag |
| `sync()` | Index un-indexed commits |
| `rebuild_index()` | Rebuild the SQLite index |

## Anomaly Detection

```python
# Detect outliers in a numeric field
anomalies = repo.anomalies("agents/alpha/state.json",
    field="confidence_score", sigma=2.0)

for a in anomalies:
    print(f"Anomaly: {a.value} (expected {a.expected_range}, severity={a.severity:.2f})")
```

## Narrative Summaries

```python
print(repo.narrate(path_pattern="agents/*"))
```

```
Between 2026-03-08 10:00 and 2026-03-08 14:00, 5 commits were recorded.

Most active files:
  - agents/alpha/state.json (3 changes)
  - agents/alpha/beliefs.json (1 change)

Event types:
  - state_updated (3)
  - beliefs_updated (1)
```

## Architecture

```
Agent -> write artifacts -> commit -> index -> query-ready
```

- **Storage**: Git (immutable, causal, content-addressed)
- **Index**: SQLite sidecar at `.gitledger/index.db` (derived, rebuildable)
- **Writes**: Synchronous (artifact write + commit)
- **Dependencies**: None (stdlib + git CLI)

## Documentation

- **[API Reference](docs/api-reference.md)** — Complete method signatures, parameters, return types, and examples
- **[User Guide](docs/user-guide.md)** — Practical walkthrough of all features with usage patterns
- **[Architecture](docs/architecture.md)** — Module overview, data flow, design decisions
- **[Changelog](CHANGELOG.md)** — Version history and release notes

## Examples

Runnable scripts in [`examples/`](examples/):

- **[basic_usage.py](examples/basic_usage.py)** — Write, commit, query timeline, semantic diff
- **[trend_and_anomalies.py](examples/trend_and_anomalies.py)** — Trend extraction and z-score anomaly detection
- **[multi_agent.py](examples/multi_agent.py)** — Multiple agents, correlation, drift, narratives
- **[wintermute_integration.py](examples/wintermute_integration.py)** — Full agent coordination system with tasks, world state, and checkpoint management

Run any example:

```bash
cd gitledger
PYTHONPATH=src python examples/basic_usage.py
```

## Memory Layer Model

GitLedger complements existing memory systems:

| Memory Layer | Purpose | Technology |
|---|---|---|
| Working Memory | Current state | Database |
| Episodic Memory | Recent events | Event tables |
| Semantic Memory | Learned knowledge | Engram systems |
| Vector Memory | Semantic retrieval | Vector databases |
| **Structural Memory** | **State evolution** | **GitLedger** |

## CI/CD

GitHub Actions workflows included:

- **CI** (`ci.yml`) — Test matrix across Python 3.10, 3.11, 3.12, 3.13
- **Release** (`release.yml`) — Publish to PyPI via trusted publishing on `v*` tags

```bash
# Tag a release
git tag v1.0.0
git push origin v1.0.0
# GitHub Actions publishes to PyPI automatically
```

## Development

```bash
git clone https://github.com/nirvanatikku/gitledger.git
cd gitledger
pip install -e ".[dev]"
make test        # run tests
make coverage    # run with coverage
make build       # build sdist + wheel
```

## License

MIT
