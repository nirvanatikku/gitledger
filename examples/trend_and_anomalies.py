"""Trend extraction and anomaly detection."""

import tempfile

from gitledger import Repo


def main():
    with Repo.init(tempfile.mkdtemp()) as repo:
        # Simulate confidence score over time
        scores = [0.85, 0.87, 0.84, 0.86, 0.88, 0.85, 0.83, 0.45, 0.86, 0.87]

        for i, score in enumerate(scores):
            repo.write("agents/alpha/state.json", {
                "confidence_score": score,
                "iteration": i,
            })
            repo.commit_event("agent-alpha", "state_updated",
                changed_paths=["agents/alpha/state.json"])

        # Extract trend
        trend = repo.trend("agents/alpha/state.json", "confidence_score")
        print("Confidence score trend:")
        for point in trend:
            print(f"  {point.timestamp.strftime('%H:%M:%S')}: {point.value}")

        # Detect anomalies
        anomalies = repo.anomalies(
            "agents/alpha/state.json",
            "confidence_score",
            sigma=2.0,
        )
        print(f"\nAnomalies detected: {len(anomalies)}")
        for a in anomalies:
            print(f"  Value {a.value} at {a.timestamp.strftime('%H:%M:%S')}")
            print(f"  Expected range: {a.expected_range[0]:.3f} - {a.expected_range[1]:.3f}")
            print(f"  Severity (z-score): {a.severity:.2f}")


if __name__ == "__main__":
    main()
