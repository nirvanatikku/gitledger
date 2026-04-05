"""Multi-agent scenario — correlation, drift detection, narratives.

Two agents operate independently. Alpha's beliefs shift, causing
a state change. GitLedger tracks everything and reveals the connections.

Run:  pip install gitledger && python examples/multi_agent.py
"""

import tempfile

from gitledger import Repo


def main():
    with Repo.init(tempfile.mkdtemp()) as repo:
        repo.write("agents/alpha/state.json", {"status": "active", "score": 0.9})
        repo.write("agents/alpha/beliefs.json", {"world_model": "stable"})
        repo.commit_event("agent-alpha", "initialized",
            changed_paths=["agents/alpha/state.json", "agents/alpha/beliefs.json"])

        repo.write("agents/beta/state.json", {"status": "active", "score": 0.8})
        repo.commit_event("agent-beta", "initialized",
            changed_paths=["agents/beta/state.json"])

        repo.write("agents/alpha/beliefs.json", {"world_model": "uncertain"})
        repo.commit_event("agent-alpha", "beliefs_updated",
            changed_paths=["agents/alpha/beliefs.json"],
            metadata={"trigger": "anomaly_detected"})

        repo.write("agents/alpha/state.json", {"status": "degraded", "score": 0.6})
        repo.commit_event("agent-alpha", "state_updated",
            changed_paths=["agents/alpha/state.json"])

        repo.commit_checkpoint()

        print("Most changed files:\n")
        for path, count in repo.most_changed(pattern="agents/*", limit=5):
            bar = "█" * count
            print(f"  {path:40s} {count} {bar}")

        print("\n\nField drift — agents/alpha/state.json:\n")
        drift = repo.drift("agents/alpha/state.json")
        for fv in drift:
            print(f"  [{fv.commit_hash[:8]}] {fv.json_path} = {fv.value!r}")

        print("\n\nSearch: 'beliefs_updated' events:\n")
        results = repo.search("beliefs_updated")
        for c in results:
            print(f"  [{c.hash[:8]}] {c.message}")

        print("\n\nNarrative summary:\n")
        print(f"  {repo.narrate(path_pattern='agents/*')}")

        print("\n\nCurrent snapshot:\n")
        snap = repo.snapshot()
        for path in sorted(snap.keys()):
            print(f"  {path}")


if __name__ == "__main__":
    main()
