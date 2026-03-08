"""Multi-agent scenario with correlation and narratives."""

import tempfile

from gitledger import Repo


def main():
    with Repo.init(tempfile.mkdtemp()) as repo:
        # Agent Alpha writes state
        repo.write("agents/alpha/state.json", {"status": "active", "score": 0.9})
        repo.write("agents/alpha/beliefs.json", {"world_model": "stable"})
        repo.commit_event("agent-alpha", "initialized",
            changed_paths=["agents/alpha/state.json", "agents/alpha/beliefs.json"])

        # Agent Beta writes state
        repo.write("agents/beta/state.json", {"status": "active", "score": 0.8})
        repo.commit_event("agent-beta", "initialized",
            changed_paths=["agents/beta/state.json"])

        # Alpha updates beliefs based on new observation
        repo.write("agents/alpha/beliefs.json", {"world_model": "uncertain"})
        repo.commit_event("agent-alpha", "beliefs_updated",
            changed_paths=["agents/alpha/beliefs.json"],
            metadata={"trigger": "anomaly_detected"})

        # Alpha updates state as a consequence
        repo.write("agents/alpha/state.json", {"status": "degraded", "score": 0.6})
        repo.commit_event("agent-alpha", "state_updated",
            changed_paths=["agents/alpha/state.json"])

        # Checkpoint
        repo.commit_checkpoint()

        # Query: which files change most?
        print("Most changed files:")
        for path, count in repo.most_changed(pattern="agents/*", limit=5):
            print(f"  {path}: {count} changes")

        # Drift detection
        print("\nField drift for agents/alpha/state.json:")
        drift = repo.drift("agents/alpha/state.json")
        for fv in drift:
            print(f"  {fv.json_path} = {fv.value}")

        # Search for belief changes
        print("\nCommits mentioning 'beliefs_updated':")
        results = repo.search("beliefs_updated")
        for c in results:
            print(f"  [{c.hash[:8]}] {c.message}")

        # Generate narrative
        print("\nNarrative:")
        print(repo.narrate(path_pattern="agents/*"))

        # Snapshot at HEAD
        print("\nCurrent snapshot:")
        snap = repo.snapshot()
        for path in sorted(snap.keys()):
            print(f"  {path}")


if __name__ == "__main__":
    main()
