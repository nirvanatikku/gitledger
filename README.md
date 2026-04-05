# GitLedger

[![PyPI](https://img.shields.io/pypi/v/gitledger)](https://pypi.org/project/gitledger/)
[![Python](https://img.shields.io/pypi/pyversions/gitledger)](https://pypi.org/project/gitledger/)
[![CI](https://github.com/nirvanatikku/gitledger/actions/workflows/ci.yml/badge.svg)](https://github.com/nirvanatikku/gitledger/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/nirvanatikku/gitledger)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen)](https://pypi.org/project/gitledger/)

**Git-native memory for agents. Every state change is a commit. Every question has an answer.**

Your agents mutate state hundreds of times a day — configs, beliefs, scores, world models. GitLedger turns every version into an immutable Git commit, then gives you a query layer on top: semantic diffs, trend extraction, anomaly detection, narrative summaries. Ask your repo *"when did confidence start dropping?"* and get a real answer.

**Zero dependencies.** Python 3.10+ and `git` on PATH. That's it.

```bash
pip install gitledger
```

## What You Can Ask

```python
repo.timeline("agents/alpha/state.json")
repo.diff("agents/alpha/state.json", commit_a, commit_b)
repo.trend("agents/alpha/state.json", "confidence_score")
repo.anomalies("agents/alpha/state.json", "confidence_score")
repo.narrate(path_pattern="agents/*")
repo.correlate("agents/alpha/state.json", "agents/beta/state.json")
```

| Query | What you get |
|---|---|
| `timeline(path)` | Every commit that touched this file, in order |
| `diff(path, a, b)` | Field-level changes: `confidence_score: 0.92 → 0.71` |
| `trend(path, field)` | Numeric values over time — spot the decline |
| `anomalies(path, field)` | Statistical outliers: `0.71 is 2.3σ below mean` |
| `narrate(pattern)` | Plain-English summary of what happened |
| `correlate(path_a, path_b)` | Find files that change together |
| `drift(path)` | Every field mutation across history |
| `search(query)` | Find commits by message content |
| `episodes(pattern)` | Group related commits into episodes |
| `most_changed(pattern)` | Hottest files by edit frequency |

## 10-Second Demo

Copy, paste, run. Creates synthetic data and immediately shows anomaly detection:

```python
from gitledger import Repo
import tempfile

with Repo.init(tempfile.mkdtemp()) as repo:
    scores = [0.85, 0.87, 0.84, 0.86, 0.88, 0.85, 0.83, 0.45, 0.86, 0.87]
    for i, s in enumerate(scores):
        repo.write("agent/state.json", {"confidence": s, "step": i})
        repo.commit_event("agent", "update", changed_paths=["agent/state.json"])

    for a in repo.anomalies("agent/state.json", "confidence", sigma=2.0):
        print(f"⚠️  Anomaly: {a.value} (expected {a.expected_range[0]:.2f}–{a.expected_range[1]:.2f}, z={a.severity:.1f})")

    trend = repo.trend("agent/state.json", "confidence")
    print(f"\n📈 {len(trend)} data points tracked across {len(scores)} commits")
```

Output:

```
⚠️  Anomaly: 0.45 (expected 0.78–0.92, z=5.2)

📈 10 data points tracked across 10 commits
```

## Quick Start

```python
from gitledger import Repo

with Repo.init("./memory") as repo:
    repo.write("agents/alpha/state.json", {
        "confidence_score": 0.85,
        "status": "active",
    })
    repo.commit_event("agent-alpha", "state_initialized",
        changed_paths=["agents/alpha/state.json"])

    repo.write("agents/alpha/state.json", {
        "confidence_score": 0.72,
        "status": "degraded",
    })
    repo.commit_event("agent-alpha", "state_updated",
        changed_paths=["agents/alpha/state.json"])

    timeline = repo.timeline("agents/alpha/state.json")
    diffs = repo.diff("agents/alpha/state.json",
        timeline[0].hash, timeline[-1].hash)

    for d in diffs:
        print(f"{d.field}: {d.old_value} → {d.new_value}")
    # confidence_score: 0.85 → 0.72
    # status: active → degraded
```

## Why Git?

Git is an unusually powerful substrate for agent memory:

- **Append-only** — commits are immutable. No state is ever lost.
- **Content-addressed** — every version has a unique hash. References are unambiguous.
- **Causal ordering** — the commit graph encodes what happened before what.
- **Diffs are native** — Git already knows how to compare any two points in time.
- **Branching** — run experiments in isolation, merge results back.
- **Inspectable** — `git log`, `git show`, `git diff` work on your memory repo. No proprietary tooling needed.
- **Reproducible** — clone the repo, you have the full history. Debug locally.

Other memory systems store the current state. Git stores *how you got there*.

## Use Cases

**Regression detection** — An agent's accuracy drops from 0.94 to 0.71 over 48 hours. `trend()` reveals the decline. `anomalies()` flags the exact commit where it crossed 2σ. `diff()` shows which fields changed.

**Agent belief tracking** — Your planning agent updates its world model every cycle. GitLedger preserves every version. When a decision goes wrong, `timeline()` reconstructs the agent's belief state at the moment it chose.

**Metric drift debugging** — A scoring pipeline's output shifts. `drift()` traces every field mutation. `correlate()` reveals that config changes upstream co-occurred with the score shift.

**Narrative summaries** — After a 6-hour run with 400 commits across 12 agents, `narrate()` produces a human-readable summary: which agents were active, what changed, which event types dominated.

**Historical state queries** — "What did the system look like at 3pm yesterday?" `snapshot(commit)` returns every file at any point in time. Full time-travel.

**Post-mortem investigation** — An operator agent made a bad call. The [investigation example](examples/investigation.py) shows a complete post-mortem: timeline reconstruction, confidence trend analysis, anomaly detection, cross-agent correlation, and root cause identification — all through GitLedger queries.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Your Agent  │────▶│   GitLedger  │────▶│     Git      │
│              │     │   (Repo)     │     │  (commits)   │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                     ┌──────▼───────┐
                     │   SQLite     │
                     │  (index.db)  │
                     └──────────────┘
```

- **Storage**: Git — immutable, causal, content-addressed
- **Index**: SQLite sidecar at `.gitledger/index.db` — derived, rebuildable
- **Reads**: Persistent `git cat-file --batch` process, batched at 200
- **Writes**: Synchronous (artifact write + commit + index)
- **Dependencies**: None (stdlib + git CLI)

## Core API

| Method | Description |
|---|---|
| `write(path, content)` | Write a JSON or text artifact |
| `commit_event(entity, event_type)` | Create a structured event commit |
| `commit_checkpoint(tag)` | Create a checkpoint with tag |
| `timeline(path, since, until)` | Commit history for a path |
| `diff(path, commit_a, commit_b)` | Semantic field-level diffs |
| `trend(path, field, since, until)` | Numeric field trends |
| `anomalies(path, field, sigma)` | Statistical outlier detection |
| `episodes(pattern, event_type, window)` | Group related commits |
| `snapshot(commit)` | All file contents at a commit |
| `drift(path, schema)` | Detect field value changes across history |
| `narrate(pattern, since, until)` | Human-readable narrative summary |
| `search(query, paths)` | Search commit messages |
| `correlate(path_a, path_b, window)` | Find co-changing paths |
| `most_changed(pattern, limit)` | Most frequently modified paths |
| `sync()` / `rebuild_index()` | Index management |

## Memory Layer Model

GitLedger fills a gap in the agent memory stack:

| Memory Layer | Purpose | Technology |
|---|---|---|
| Working Memory | Current state | Database |
| Episodic Memory | Recent events | Event tables |
| Semantic Memory | Learned knowledge | Engram systems |
| Vector Memory | Semantic retrieval | Vector databases |
| **Structural Memory** | **State evolution over time** | **GitLedger** |

## Examples

Runnable scripts in [`examples/`](examples/):

| Example | What it shows |
|---|---|
| **[basic_usage.py](examples/basic_usage.py)** | Write, commit, query timeline, semantic diff |
| **[trend_and_anomalies.py](examples/trend_and_anomalies.py)** | Trend extraction, z-score anomaly detection with flagged outliers |
| **[multi_agent.py](examples/multi_agent.py)** | Multiple agents, correlation, drift detection, narrative summaries |
| **[investigation.py](examples/investigation.py)** | Full post-mortem: 3 agents, a failure, and every query method used to reconstruct what went wrong |
| **[wintermute_integration.py](examples/wintermute_integration.py)** | Agent coordination with tasks, world state, and checkpoints |

```bash
pip install gitledger
PYTHONPATH=src python examples/investigation.py
```

<!-- TODO: Add a GIF/recording of the investigation example running — the terminal output is dramatic and reads like a story. Asciinema or terminalizer would work well here. -->

## Documentation

- **[Full Documentation](https://nirvanatikku.github.io/gitledger/)** — User guide, API reference, architecture
- **[API Reference](docs/api-reference.md)** — Complete method signatures and examples
- **[User Guide](docs/user-guide.md)** — Practical walkthrough of all features
- **[Architecture](docs/architecture.md)** — Module overview, data flow, design decisions
- **[Changelog](CHANGELOG.md)** — Version history
- **[llms.txt](llms.txt)** — Agent-readable documentation

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
