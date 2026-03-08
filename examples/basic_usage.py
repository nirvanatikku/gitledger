"""Basic GitLedger usage — write, commit, query."""

import tempfile

from gitledger import Repo


def main():
    with Repo.init(tempfile.mkdtemp()) as repo:
        # Write agent state
        repo.write("agents/alpha/state.json", {
            "confidence_score": 0.85,
            "status": "active",
            "tasks_completed": 10,
        })
        repo.commit_event("agent-alpha", "state_initialized",
            changed_paths=["agents/alpha/state.json"])

        # Update state
        repo.write("agents/alpha/state.json", {
            "confidence_score": 0.90,
            "status": "active",
            "tasks_completed": 12,
        })
        repo.commit_event("agent-alpha", "state_updated",
            changed_paths=["agents/alpha/state.json"])

        # Query the timeline
        timeline = repo.timeline("agents/alpha/state.json")
        print(f"Timeline has {len(timeline)} commits:")
        for commit in timeline:
            print(f"  [{commit.hash[:8]}] {commit.message}")

        # Semantic diff between first and last
        diffs = repo.diff(
            "agents/alpha/state.json",
            timeline[0].hash,
            timeline[-1].hash,
        )
        print(f"\nChanges ({timeline[0].hash[:8]} -> {timeline[-1].hash[:8]}):")
        for d in diffs:
            print(f"  {d.field}: {d.old_value} -> {d.new_value}")


if __name__ == "__main__":
    main()
