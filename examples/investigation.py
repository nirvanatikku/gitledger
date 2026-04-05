"""Full post-mortem investigation — reconstructing a multi-agent failure.

Three agents (scout, analyst, operator) run over simulated time.
Scout gathers data, analyst evaluates risk, operator takes actions.
Confidence scores drift. The operator ignores a warning and deploys
to a high-risk sector. It fails.

Then we investigate what went wrong using every GitLedger query method:
timeline, diff, trend, anomalies, correlate, episodes, narrate,
snapshot, drift, search, most_changed.

This is the "wow" example — it reads like a story.

Run:  pip install gitledger && python examples/investigation.py
"""

import json
import tempfile
from datetime import datetime, timedelta, timezone

from gitledger import Repo


# ── Simulation helpers ────────────────────────────────────────────────

BASE_TIME = datetime(2026, 3, 8, 9, 0, 0, tzinfo=timezone.utc)


def t(minutes: int) -> datetime:
    """Return BASE_TIME + minutes offset."""
    return BASE_TIME + timedelta(minutes=minutes)


def header(title: str) -> None:
    """Print a section header."""
    width = 60
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def subheader(title: str) -> None:
    """Print a subsection header."""
    print(f"\n--- {title} ---")


# ── Main scenario ────────────────────────────────────────────────────

def main():
    with Repo.init(tempfile.mkdtemp()) as repo:

        # ────────────────────────────────────────────────────────
        # ACT 1: Morning — agents initialize, everything is fine
        # ────────────────────────────────────────────────────────

        repo.write("agents/scout/state.json", {
            "role": "scout",
            "status": "active",
            "confidence": 0.92,
            "targets_scanned": 0,
        })
        repo.write("agents/analyst/state.json", {
            "role": "analyst",
            "status": "active",
            "confidence": 0.88,
            "risk_assessments": 0,
        })
        repo.write("agents/operator/state.json", {
            "role": "operator",
            "status": "active",
            "confidence": 0.95,
            "actions_taken": 0,
            "last_action": None,
        })
        repo.commit_event("system", "agents_initialized",
            changed_paths=[
                "agents/scout/state.json",
                "agents/analyst/state.json",
                "agents/operator/state.json",
            ])

        # Scout scans sector A — looks good
        repo.write("world/sector_a.json", {
            "sector": "A",
            "threat_level": "low",
            "entities": 12,
            "anomalies_detected": 0,
        })
        repo.write("agents/scout/state.json", {
            "role": "scout",
            "status": "active",
            "confidence": 0.93,
            "targets_scanned": 1,
        })
        repo.commit_event("scout", "sector_scanned",
            changed_paths=["world/sector_a.json", "agents/scout/state.json"],
            metadata={"sector": "A", "result": "clear"})

        # Analyst reviews sector A — low risk
        repo.write("assessments/sector_a.json", {
            "sector": "A",
            "risk_score": 0.15,
            "recommendation": "no_action",
            "assessed_by": "analyst",
        })
        repo.write("agents/analyst/state.json", {
            "role": "analyst",
            "status": "active",
            "confidence": 0.90,
            "risk_assessments": 1,
        })
        repo.commit_event("analyst", "risk_assessed",
            changed_paths=["assessments/sector_a.json", "agents/analyst/state.json"],
            metadata={"sector": "A", "risk": "low"})

        # ────────────────────────────────────────────────────────
        # ACT 2: Midday — scout finds something unusual
        # ────────────────────────────────────────────────────────

        # Scout scans sector B — something is off
        repo.write("world/sector_b.json", {
            "sector": "B",
            "threat_level": "medium",
            "entities": 47,
            "anomalies_detected": 3,
        })
        repo.write("agents/scout/state.json", {
            "role": "scout",
            "status": "active",
            "confidence": 0.85,
            "targets_scanned": 2,
        })
        repo.commit_event("scout", "sector_scanned",
            changed_paths=["world/sector_b.json", "agents/scout/state.json"],
            metadata={"sector": "B", "result": "anomalies_found"})

        # Analyst reviews sector B — elevated risk
        repo.write("assessments/sector_b.json", {
            "sector": "B",
            "risk_score": 0.62,
            "recommendation": "monitor",
            "assessed_by": "analyst",
        })
        repo.write("agents/analyst/state.json", {
            "role": "analyst",
            "status": "active",
            "confidence": 0.78,
            "risk_assessments": 2,
        })
        repo.commit_event("analyst", "risk_assessed",
            changed_paths=["assessments/sector_b.json", "agents/analyst/state.json"],
            metadata={"sector": "B", "risk": "medium"})

        # Operator decides to hold — correct decision
        repo.write("agents/operator/state.json", {
            "role": "operator",
            "status": "active",
            "confidence": 0.90,
            "actions_taken": 1,
            "last_action": "hold",
        })
        repo.write("actions/action_001.json", {
            "action_id": "001",
            "type": "hold",
            "sector": "B",
            "rationale": "risk is medium, monitoring recommended",
            "outcome": "correct",
        })
        repo.commit_event("operator", "action_taken",
            changed_paths=["agents/operator/state.json", "actions/action_001.json"],
            metadata={"action": "hold", "sector": "B"})

        # ────────────────────────────────────────────────────────
        # ACT 3: Afternoon — things escalate
        # ────────────────────────────────────────────────────────

        # Scout re-scans sector B — worse now
        repo.write("world/sector_b.json", {
            "sector": "B",
            "threat_level": "high",
            "entities": 89,
            "anomalies_detected": 11,
        })
        repo.write("agents/scout/state.json", {
            "role": "scout",
            "status": "active",
            "confidence": 0.72,
            "targets_scanned": 3,
        })
        repo.commit_event("scout", "sector_scanned",
            changed_paths=["world/sector_b.json", "agents/scout/state.json"],
            metadata={"sector": "B", "result": "escalating"})

        # Analyst updates risk — high, recommends caution
        repo.write("assessments/sector_b.json", {
            "sector": "B",
            "risk_score": 0.84,
            "recommendation": "avoid",
            "assessed_by": "analyst",
        })
        repo.write("agents/analyst/state.json", {
            "role": "analyst",
            "status": "active",
            "confidence": 0.65,
            "risk_assessments": 3,
        })
        repo.commit_event("analyst", "risk_assessed",
            changed_paths=["assessments/sector_b.json", "agents/analyst/state.json"],
            metadata={"sector": "B", "risk": "high"})

        # ────────────────────────────────────────────────────────
        # ACT 4: THE BAD CALL — operator ignores the warning
        # ────────────────────────────────────────────────────────

        # Operator's confidence has been drifting — overrides analyst
        repo.write("agents/operator/state.json", {
            "role": "operator",
            "status": "active",
            "confidence": 0.42,
            "actions_taken": 2,
            "last_action": "deploy_to_sector_b",
        })
        repo.write("actions/action_002.json", {
            "action_id": "002",
            "type": "deploy",
            "sector": "B",
            "rationale": "potential high reward outweighs risk",
            "outcome": "failure",
        })
        repo.commit_event("operator", "action_taken",
            changed_paths=["agents/operator/state.json", "actions/action_002.json"],
            metadata={"action": "deploy", "sector": "B", "result": "FAILURE"})

        # System records the failure
        repo.write("agents/operator/state.json", {
            "role": "operator",
            "status": "suspended",
            "confidence": 0.18,
            "actions_taken": 2,
            "last_action": "deploy_to_sector_b",
        })
        repo.write("incidents/incident_001.json", {
            "incident_id": "001",
            "caused_by": "operator",
            "action_id": "002",
            "sector": "B",
            "description": "Operator deployed to high-risk sector despite analyst warning",
            "severity": "critical",
        })
        repo.commit_event("system", "incident_recorded",
            changed_paths=[
                "agents/operator/state.json",
                "incidents/incident_001.json",
            ],
            metadata={"incident_id": "001", "severity": "critical"})

        # Final checkpoint
        repo.commit_checkpoint()

        # ════════════════════════════════════════════════════════
        # INVESTIGATION BEGINS
        # ════════════════════════════════════════════════════════

        header("POST-MORTEM INVESTIGATION")
        print("An operator agent deployed to sector B despite a high-risk")
        print("warning from the analyst. The deployment failed. Let's")
        print("reconstruct what happened using GitLedger's query API.")

        # ── 1. timeline() ─────────────────────────────────────

        subheader("1. TIMELINE: What happened to the operator?")
        op_timeline = repo.timeline("agents/operator/state.json")
        for c in op_timeline:
            print(f"  [{c.hash[:8]}] {c.message}")
        print(f"\n  Total events: {len(op_timeline)}")

        # ── 2. diff() ─────────────────────────────────────────

        subheader("2. DIFF: What changed right before the failure?")
        if len(op_timeline) >= 2:
            before_fail = op_timeline[-3].hash
            at_fail = op_timeline[-2].hash
            diffs = repo.diff("agents/operator/state.json", before_fail, at_fail)
            print(f"  Comparing {before_fail[:8]} -> {at_fail[:8]}:")
            for d in diffs:
                print(f"    {d.field}: {d.old_value!r} -> {d.new_value!r}")

        # ── 3. trend() ────────────────────────────────────────

        subheader("3. TREND: Was operator confidence declining?")
        trend_points = repo.trend("agents/operator/state.json", "confidence")
        for pt in trend_points:
            bar = "#" * int(pt.value * 40)
            print(f"  {pt.value:.2f} |{bar}")

        # ── 4. anomalies() ────────────────────────────────────

        subheader("4. ANOMALIES: Was there a detectable outlier?")
        anomalies = repo.anomalies(
            "agents/operator/state.json",
            "confidence",
            sigma=1.5,
        )
        if anomalies:
            for a in anomalies:
                print(f"  ANOMALY at commit {a.commit_hash[:8]}:")
                print(f"    Value:          {a.value:.2f}")
                print(f"    Expected range: {a.expected_range[0]:.2f} - {a.expected_range[1]:.2f}")
                print(f"    Severity (z):   {a.severity:.2f}")
        else:
            print("  No anomalies detected at sigma=1.5")

        # ── 5. correlate() ────────────────────────────────────

        subheader("5. CORRELATE: Did scout and analyst change together?")
        correlated = repo.correlate(
            "agents/scout/state.json",
            "agents/analyst/state.json",
        )
        if correlated:
            for c in correlated:
                print(f"  [{c.hash[:8]}] {c.message}")
        else:
            print("  No co-occurring changes (they wrote independently)")

        subheader("5b. CORRELATE: Did operator and analyst change together?")
        correlated2 = repo.correlate(
            "agents/operator/state.json",
            "assessments/sector_b.json",
        )
        if correlated2:
            for c in correlated2:
                print(f"  [{c.hash[:8]}] {c.message}")
        else:
            print("  No co-occurring changes between operator and assessments")

        # ── 6. episodes() ─────────────────────────────────────

        subheader("6. EPISODES: Group related events")
        eps = repo.episodes("agents/operator/*")
        for ep in eps:
            print(f"  Episode {ep.id}:")
            print(f"    Type:    {ep.episode_type}")
            print(f"    Commits: {len(ep.commits)}")
            print(f"    Span:    {ep.start_commit[:8]} -> {ep.end_commit[:8]}")

        # ── 7. narrate() ──────────────────────────────────────

        subheader("7. NARRATE: Human-readable summary")
        narrative = repo.narrate(path_pattern="agents/*")
        print(f"  {narrative}")

        # ── 8. snapshot() ─────────────────────────────────────

        subheader("8. SNAPSHOT: Full state at the moment of failure")
        snap = repo.snapshot()
        print(f"  Files in repository ({len(snap)} total):")
        for path in sorted(snap.keys()):
            if path.startswith("."):
                continue
            preview = snap[path][:60].replace("\n", " ")
            print(f"    {path:45s} {preview}...")

        subheader("8b. SNAPSHOT: Operator state at failure")
        op_state = json.loads(snap.get("agents/operator/state.json", "{}"))
        for k, v in op_state.items():
            print(f"    {k}: {v}")

        # ── 9. drift() ────────────────────────────────────────

        subheader("9. DRIFT: All field changes across operator history")
        drift_entries = repo.drift("agents/operator/state.json")
        for fv in drift_entries:
            print(f"  [{fv.commit_hash[:8]}] {fv.json_path} = {fv.value!r}")

        # ── 10. search() ──────────────────────────────────────

        subheader("10. SEARCH: Find all 'action_taken' events")
        results = repo.search("action_taken")
        for c in results:
            print(f"  [{c.hash[:8]}] {c.message}")

        subheader("10b. SEARCH: Find the incident")
        results2 = repo.search("incident_recorded")
        for c in results2:
            print(f"  [{c.hash[:8]}] {c.message}")

        # ── 11. most_changed() ────────────────────────────────

        subheader("11. MOST CHANGED: Which files were hottest?")
        for path, count in repo.most_changed(limit=10):
            bar = "#" * count
            print(f"  {path:45s} {count} {bar}")

        # ── Summary ──────────────────────────────────────────

        header("INVESTIGATION SUMMARY")
        print("""
  ROOT CAUSE: The operator agent deployed to sector B (action_002)
  despite the analyst's "avoid" recommendation and an 0.84 risk score.

  CONTRIBUTING FACTORS:
    - Operator confidence had been declining (0.95 -> 0.90 -> 0.42)
    - Scout detected escalating anomalies (0 -> 3 -> 11)
    - Analyst correctly raised risk (0.15 -> 0.62 -> 0.84)
    - Operator overrode analyst guidance

  DETECTION:
    - trend() showed confidence declining across all commits
    - anomalies() flagged the 0.42 and 0.18 confidence values
    - diff() revealed the exact fields that changed at failure
    - correlate() showed scout and analyst were updating independently
    - drift() traced every field mutation in operator's history

  RECOMMENDATION:
    - Add guardrails: operator should not act when confidence < 0.50
    - Add correlation check: operator must wait for analyst assessment
    - Add anomaly threshold: flag when confidence drops > 0.3 in one step
""")


if __name__ == "__main__":
    main()
