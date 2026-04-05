"""Basic GitLedger usage — write state, commit events, query history.

Run:  pip install gitledger && python examples/basic_usage.py
"""

import tempfile

from gitledger import Repo


def main():
    with Repo.init(tempfile.mkdtemp()) as repo:
        repo.write("agents/alpha/state.json", {
            "confidence_score": 0.85,
            "status": "active",
            "tasks_completed": 10,
        })
        repo.commit_event("agent-alpha", "state_initialized",
            changed_paths=["agents/alpha/state.json"])

        repo.write("agents/alpha/state.json", {
            "confidence_score": 0.90,
            "status": "active",
            "tasks_completed": 12,
        })
        repo.commit_event("agent-alpha", "state_updated",
            changed_paths=["agents/alpha/state.json"])

        repo.write("agents/alpha/state.json", {
            "confidence_score": 0.72,
            "status": "degraded",
            "tasks_completed": 14,
        })
        repo.commit_event("agent-alpha", "state_updated",
            changed_paths=["agents/alpha/state.json"])

        timeline = repo.timeline("agents/alpha/state.json")
        print(f"Timeline: {len(timeline)} commits\n")
        for commit in timeline:
            print(f"  [{commit.hash[:8]}] {commit.message}")

        print(f"\nSemantic diff (first → last):")
        diffs = repo.diff(
            "agents/alpha/state.json",
            timeline[0].hash,
            timeline[-1].hash,
        )
        for d in diffs:
            print(f"  {d.field}: {d.old_value} → {d.new_value}")

        print(f"\nTrend for confidence_score:")
        trend = repo.trend("agents/alpha/state.json", "confidence_score")
        for pt in trend:
            bar = "█" * int(pt.value * 30)
            print(f"  {pt.value:.2f} {bar}")


if __name__ == "__main__":
    main()
