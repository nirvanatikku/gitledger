# GitLedger

**Your agents do things. GitLedger remembers what, when, and why.**

A Python library that gives agents and automated systems persistent, structured memory built on Git.
Every state change becomes an immutable commit. Every question about the past has an answer.

Zero dependencies. Only Python 3.10+ and git on PATH.

```bash
pip install gitledger
```

---

## The problem

Agents make decisions, update state, and interact with the world hundreds of times a day. But most systems only keep the latest state. When something breaks, you're left asking:

- **What did the agent believe 2 hours ago?**
- **When did the confidence score start dropping?**
- **Which state change triggered the cascade failure?**

Databases give you current state but not history. Logs give you history but no structure. GitLedger gives you both: structured state that you can query across time.

---

## Not line diffs. Field diffs.

Traditional diffs tell you which *lines* changed. That's useless when your agent's state is a JSON object. GitLedger diffs at the **field level** — so you see exactly which values changed and what they were.

**Traditional line diff:**

```diff
 {
-  "confidence_score": 0.85,
+  "confidence_score": 0.72,
-  "status": "active",
+  "status": "degraded",
   "tasks_completed": 13
 }
```

*Which lines changed? Sure. But what actually happened?*

**GitLedger semantic diff:**

```
confidence_score: 0.85 → 0.72
status: "active" → "degraded"
```

Queryable, structured, and works on nested fields: `config.retry`, `items[2].score`.

---

## Who it's for

### For humans

You're building systems that run autonomously. You need to understand what they're doing without reading raw logs or querying five different databases.

- Audit any agent's decision history with a single query
- Debug production issues by reconstructing exact state at any point in time
- Track drift in agent behavior with semantic diffs, not line diffs
- Get alerted when metrics move outside normal ranges
- Generate human-readable narratives of what happened and when

### For agents

Your agent needs memory that persists across restarts, supports temporal reasoning, and doesn't require another infrastructure dependency to manage.

- Read back your own state history to inform future decisions
- Compare current beliefs against past beliefs to detect drift
- Correlate changes across multiple entities to find causal patterns
- Recover from crashes by replaying from any checkpoint
- Zero dependencies means nothing extra to install or configure

---

## The missing layer

GitLedger is the missing layer: a structured, queryable history of every state change your system has ever made. Built on Git, so you get immutability, content addressing, and branching for free. No infrastructure to manage, no dependencies to install.

| Memory Layer | Purpose | Technology |
|---|---|---|
| Working Memory | Current system state | Database |
| Episodic Memory | Recent event traces | Event tables |
| Semantic Memory | Learned knowledge | Engram systems |
| Vector Memory | Semantic retrieval | Vector databases |
| **Structural Memory** | **Full state evolution history** | **GitLedger** |

---

## Quick start

```python
from gitledger import Repo

# Initialize a new repository
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

---

## What you can do

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
