"""Example: GitLedger as memory substrate for a Wintermute-style system.

Demonstrates the recommended repository layout for agent coordination
systems, with structured state management and temporal queries.
"""

import json
import tempfile

from gitledger import Repo


def main():
    with Repo.init(tempfile.mkdtemp()) as repo:
        # --- System Bootstrap ---
        repo.write("system/governance.json", {
            "version": "1.0",
            "max_agents": 10,
            "checkpoint_interval_minutes": 5,
        })
        repo.write("world/state.json", {
            "environment": "production",
            "entities_count": 0,
            "last_scan": None,
        })
        repo.commit_event("system", "bootstrapped",
            changed_paths=["system/governance.json", "world/state.json"])

        # --- Agent Registration ---
        for agent_id in ["planner", "observer", "executor"]:
            repo.write(f"agents/{agent_id}/config.json", {
                "role": agent_id,
                "active": True,
                "created_by": "system",
            })
            repo.write(f"agents/{agent_id}/state.json", {
                "status": "idle",
                "confidence": 1.0,
                "tasks_completed": 0,
            })
            repo.commit_event(agent_id, "registered",
                changed_paths=[
                    f"agents/{agent_id}/config.json",
                    f"agents/{agent_id}/state.json",
                ])

        # --- Observer scans world ---
        repo.write("world/entities.json", {
            "entities": [
                {"id": "e1", "type": "service", "status": "healthy"},
                {"id": "e2", "type": "service", "status": "degraded"},
            ],
        })
        repo.write("world/state.json", {
            "environment": "production",
            "entities_count": 2,
            "last_scan": "2026-03-08T14:00:00Z",
        })
        repo.write("agents/observer/state.json", {
            "status": "active",
            "confidence": 0.95,
            "tasks_completed": 1,
        })
        repo.commit_event("observer", "world_scanned",
            changed_paths=["world/entities.json", "world/state.json",
                           "agents/observer/state.json"],
            metadata={"entities_found": 2, "degraded": 1})

        # --- Planner creates a task ---
        repo.write("tasks/fix-e2/runs.json", {
            "task_id": "fix-e2",
            "status": "pending",
            "assigned_to": "executor",
            "created_by": "planner",
            "target_entity": "e2",
        })
        repo.write("agents/planner/state.json", {
            "status": "active",
            "confidence": 0.88,
            "tasks_completed": 1,
        })
        repo.commit_event("planner", "task_created",
            changed_paths=["tasks/fix-e2/runs.json",
                           "agents/planner/state.json"],
            metadata={"task_id": "fix-e2"})

        # --- Executor runs the task ---
        repo.write("tasks/fix-e2/runs.json", {
            "task_id": "fix-e2",
            "status": "completed",
            "assigned_to": "executor",
            "created_by": "planner",
            "target_entity": "e2",
            "result": "service restarted",
        })
        repo.write("agents/executor/state.json", {
            "status": "active",
            "confidence": 0.92,
            "tasks_completed": 1,
        })
        repo.commit_event("executor", "task_completed",
            changed_paths=["tasks/fix-e2/runs.json",
                           "agents/executor/state.json"],
            metadata={"task_id": "fix-e2", "result": "success"})

        # --- Checkpoint ---
        repo.commit_checkpoint()

        # --- Queries ---
        print("=== System Narrative ===")
        print(repo.narrate())
        print()

        print("=== Most Changed Files ===")
        for path, count in repo.most_changed(limit=5):
            print(f"  {path}: {count}")
        print()

        print("=== Observer State Timeline ===")
        for c in repo.timeline("agents/observer/state.json"):
            print(f"  [{c.hash[:8]}] {c.message}")
        print()

        print("=== Task Fix-E2 Timeline ===")
        for c in repo.timeline("tasks/fix-e2/runs.json"):
            print(f"  [{c.hash[:8]}] {c.message}")

        # Diff the task from creation to completion
        task_tl = repo.timeline("tasks/fix-e2/runs.json")
        if len(task_tl) >= 2:
            print(f"\n=== Task Diff (created -> completed) ===")
            diffs = repo.diff("tasks/fix-e2/runs.json",
                task_tl[0].hash, task_tl[-1].hash)
            for d in diffs:
                print(f"  {d.field}: {d.old_value!r} -> {d.new_value!r}")

        print(f"\n=== Snapshot (file count: {len(repo.snapshot())}) ===")
        for path in sorted(repo.snapshot().keys()):
            print(f"  {path}")


if __name__ == "__main__":
    main()
