# User Guide

A practical guide to using GitLedger as a structural memory system.

---

## Installation

```bash
pip install gitledger
```

**Requirements:**
- Python 3.10+
- Git installed and available on PATH

GitLedger has **zero Python dependencies**. It uses only the standard library and the git CLI.

---

## Core Concepts

### What Is Structural Memory?

GitLedger provides **structural temporal memory** — full state evolution history backed by Git.

Unlike databases (current state) or vector stores (semantic retrieval), GitLedger answers: **what happened, and how did the system evolve?**

| Memory Layer | Purpose | Technology |
|---|---|---|
| Working Memory | Current state | Database |
| Episodic Memory | Recent events | Event tables |
| Semantic Memory | Learned knowledge | Engram systems |
| Vector Memory | Semantic retrieval | Vector databases |
| **Structural Memory** | **State evolution** | **GitLedger** |

### How It Works

1. **Agents write structured artifacts** (JSON files) to a Git repository
2. **Commits capture state transitions** with structured metadata
3. **A SQLite sidecar index** enables fast temporal queries
4. **The Python API** provides high-level query primitives

The index lives at `.gitledger/index.db` and is fully derived from Git history — it can be rebuilt at any time.

---

## Getting Started

### Create a Repository

```python
from gitledger import Repo

repo = Repo.init("./memory")
```

This creates a new Git repository and initializes the GitLedger index.

### Open an Existing Repository

```python
repo = Repo("./memory")
```

If the repository has commits that haven't been indexed yet (e.g., after cloning), sync the index:

```python
repo.sync()
```

---

## Writing Artifacts

### Write Files

```python
repo.write("agents/alpha/state.json", {
    "confidence_score": 0.85,
    "status": "active",
    "tasks_completed": 10,
})
```

`write()` accepts dicts, lists, or raw strings. Dicts and lists are serialized to JSON.

You can write multiple files before committing:

```python
repo.write("agents/alpha/state.json", {"confidence_score": 0.90})
repo.write("agents/alpha/beliefs.json", {"world_model": "stable"})
```

### Commit Changes

#### Event Commits

Event commits represent meaningful state transitions:

```python
repo.commit_event(
    "agent-alpha",
    "beliefs_updated",
    changed_paths=["agents/alpha/beliefs.json"],
    metadata={"trigger": "new_observation"},
)
```

This creates a commit with message `event:agent-alpha:beliefs_updated` and structured JSON metadata in the body.

#### Checkpoint Commits

Checkpoints are periodic stable reference points:

```python
repo.commit_checkpoint()
```

This creates a commit and an annotated Git tag for efficient timeline traversal.

---

## Querying History

### Timelines

Get the full commit history for a specific file:

```python
timeline = repo.timeline("agents/alpha/state.json")

for commit in timeline:
    print(f"{commit.timestamp}: {commit.message}")
```

Filter by time range:

```python
from datetime import datetime, timedelta, timezone

recent = repo.timeline(
    "agents/alpha/state.json",
    since=datetime.now(tz=timezone.utc) - timedelta(hours=24),
)
```

### Semantic Diffs

Compare two versions of a file at the field level:

```python
timeline = repo.timeline("agents/alpha/state.json")
diffs = repo.diff(
    "agents/alpha/state.json",
    commit_a=timeline[0].hash,
    commit_b=timeline[-1].hash,
)

for d in diffs:
    print(f"{d.field}: {d.old_value} -> {d.new_value}")
```

Output:
```
confidence_score: 0.85 -> 0.72
status: active -> degraded
tasks_completed: 10 -> 13
```

This works for nested JSON — fields are expressed as dot-paths like `config.retry` or `items[2]`.

### Trends

Track a numeric field across commits:

```python
trend = repo.trend("agents/alpha/state.json", "confidence_score")

for point in trend:
    print(f"{point.timestamp}: {point.value}")
```

### Anomaly Detection

Detect statistical outliers in a trend:

```python
anomalies = repo.anomalies(
    "agents/alpha/state.json",
    "confidence_score",
    sigma=2.0,  # z-score threshold
)

for a in anomalies:
    print(f"Anomaly at {a.timestamp}: {a.value} "
          f"(expected {a.expected_range[0]:.2f}-{a.expected_range[1]:.2f}, "
          f"severity={a.severity:.2f})")
```

### Snapshots

Get all file contents at a specific commit:

```python
snap = repo.snapshot()  # HEAD
# or
snap = repo.snapshot("abc123")

import json
state = json.loads(snap["agents/alpha/state.json"])
```

### Narratives

Generate human-readable summaries:

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

### Search

Find commits by message content:

```python
results = repo.search("beliefs_updated")
```

Optionally restrict to commits that touched specific files:

```python
results = repo.search("updated", paths=["agents/alpha/*"])
```

### Correlation

Find commits that changed two files together:

```python
correlated = repo.correlate(
    "agents/alpha/state.json",
    "agents/alpha/beliefs.json",
)
```

### Drift Detection

Track which fields changed across a file's history:

```python
drift = repo.drift("agents/alpha/state.json")

for fv in drift:
    print(f"Commit {fv.commit_hash[:8]}: {fv.json_path} = {fv.value}")
```

### Most Changed Files

Find the hottest files in the repository:

```python
top = repo.most_changed(pattern="agents/*", limit=5)

for path, count in top:
    print(f"{path}: {count} changes")
```

---

## Repository Layout

GitLedger works with any repository structure, but the recommended layout for agent systems is:

```
/agents/{agent_id}/
    state.json
    beliefs.json
    plans.json
    config.json

/tasks/{task_id}/
    runs.json

/workflows/{workflow_id}/
    result.json

/world/
    state.json
    entities.json

/system/
    governance.json
    schema_manifest.json
```

---

## Index Management

The SQLite index at `.gitledger/index.db` is derived from Git and can always be rebuilt:

```python
# Index any new commits
count = repo.sync()
print(f"Indexed {count} new commits")

# Full rebuild from scratch
count = repo.rebuild_index()
print(f"Rebuilt index with {count} commits")
```

Add `.gitledger/` to your `.gitignore` — the index is local and rebuildable.

---

## Context Manager

Always use the context manager to ensure the database connection is closed:

```python
with Repo("./memory") as repo:
    timeline = repo.timeline("agents/alpha/state.json")
    # ... do work
# connection closed automatically
```

---

## Performance Considerations

GitLedger scales well for:
- Millions of commits
- Small structured artifacts (<100KB per file)
- Path-scoped queries

Avoid:
- Storing large binary blobs
- Writing execution logs to Git
- Committing excessively granular state mutations
- Scanning entire commit history without path filtering

### Understanding the Bottlenecks

The two serialization points are:

1. **Git's `index.lock`** — only one process can write to a git repo at a time. Every `write()` + `commit_event()` takes the lock.
2. **SQLite single-writer** — indexing each commit writes to the sidecar database.

With a single repo and one-agent-per-commit, this means:

| Agents | Commit cycle | Commits/min | Feasibility |
|--------|-------------|-------------|-------------|
| 10     | 1 min       | 10          | Comfortable |
| 50     | 1 min       | 50          | Fine        |
| 150    | 1 min       | 150         | Needs batching or sharding |
| 150    | 5 min       | 30          | Comfortable |

### Scaling to 150 Agents

Three strategies, from simplest to most involved:

#### 1. Batch Commits (simplest — no code changes)

Instead of each agent committing independently, batch multiple agents' state changes into a single commit. One commit can touch 150 files:

```python
with Repo("./memory") as repo:
    for agent in agents:
        repo.write(f"agents/{agent.id}/state.json", agent.state)
    repo.commit_event("system", "batch_update", 
                      changed_paths=[f"agents/{a.id}/state.json" for a in agents])
```

This reduces 150 commits to 1. Git handles multi-file commits with zero additional overhead. Queries by path still work exactly the same — `timeline("agents/alpha/state.json")` only returns commits that touched that path.

Trade-off: you lose per-agent commit granularity (all 150 changes share one timestamp). If you need per-agent attribution, include agent IDs in the commit metadata.

#### 2. Shard by Agent Group (moderate — multiple repos)

Split agents across multiple repositories by team, function, or arbitrary partition:

```python
repos = {
    "planning": Repo("./memory-planning"),     # agents 1-50
    "execution": Repo("./memory-execution"),    # agents 51-100
    "monitoring": Repo("./memory-monitoring"),  # agents 101-150
}

repo = repos[agent.group]
repo.write(f"agents/{agent.id}/state.json", agent.state)
repo.commit_event(agent.id, "state_updated")
```

Each repo gets its own `index.lock` and SQLite index — zero contention between groups. 50 agents per repo is well within comfortable limits.

Trade-off: cross-group queries (e.g., "which agents across all groups changed in the last hour?") require querying multiple repos and merging results.

#### 3. Write Queue (most control — single writer process)

Funnel all writes through a single writer process with a queue:

```python
import queue, threading

write_queue = queue.Queue()

def writer_loop(repo):
    while True:
        batch = [write_queue.get()]
        # Drain the queue for batching
        while not write_queue.empty():
            batch.append(write_queue.get_nowait())
        for item in batch:
            repo.write(item["path"], item["content"])
        repo.commit_event("system", "batch_update",
                          changed_paths=[i["path"] for i in batch])

# Agents enqueue writes — never block on git
write_queue.put({"path": f"agents/{agent_id}/state.json", "content": state})
```

This gives you single-repo simplicity with serialized writes and natural batching. The queue absorbs bursts — if 20 agents write in the same 100ms window, they collapse into one commit.

Trade-off: adds infrastructure (a writer thread/process). Writes are eventually consistent rather than synchronous.

### Additional Scaling Tactics

- **Shard repositories by time** — archive historical repos quarterly/yearly, start fresh. Old repos remain queryable.
- **Incremental indexing** — `sync()` only indexes new commits since the last sync, not the full history.
- **Path-scoped queries** — all query methods accept path filters. Always use them.
- **Longer commit cycles** — moving from 1-minute to 5-minute cycles reduces write pressure by 5x with minimal information loss for most use cases.
