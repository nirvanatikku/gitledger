"""Trend extraction and anomaly detection — spot the outlier.

Simulates an agent whose confidence score is stable around 0.85,
then suddenly drops to 0.45 for one iteration before recovering.
GitLedger's anomaly detection flags it automatically.

Run:  pip install gitledger && python examples/trend_and_anomalies.py
"""

import tempfile

from gitledger import Repo


def main():
    with Repo.init(tempfile.mkdtemp()) as repo:
        scores = [0.85, 0.87, 0.84, 0.86, 0.88, 0.85, 0.83, 0.45, 0.86, 0.87]

        for i, score in enumerate(scores):
            repo.write("agents/alpha/state.json", {
                "confidence_score": score,
                "iteration": i,
            })
            repo.commit_event("agent-alpha", "state_updated",
                changed_paths=["agents/alpha/state.json"])

        print("Confidence score over time:\n")
        trend = repo.trend("agents/alpha/state.json", "confidence_score")
        for point in trend:
            bar = "█" * int(point.value * 40)
            marker = " ← anomaly" if point.value < 0.5 else ""
            print(f"  {point.value:.2f} {bar}{marker}")

        anomalies = repo.anomalies(
            "agents/alpha/state.json",
            "confidence_score",
            sigma=2.0,
        )
        print(f"\nAnomalies detected: {len(anomalies)}\n")
        for a in anomalies:
            print(f"  ⚠️  Value:    {a.value}")
            print(f"     Expected: {a.expected_range[0]:.3f} – {a.expected_range[1]:.3f}")
            print(f"     Severity: {a.severity:.2f}σ from mean")
            print(f"     Commit:   {a.commit_hash[:8]}")


if __name__ == "__main__":
    main()
