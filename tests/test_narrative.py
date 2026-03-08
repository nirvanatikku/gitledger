"""Tests for narrative generation."""

from datetime import datetime, timezone

from gitledger.models import ChangeType, Commit, FileChange
from gitledger.narrative import narrate


class TestNarrate:
    def test_basic_narrative(self):
        commits = [
            Commit("abc", datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc), "event:alpha:init", "alice"),
            Commit("def", datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc), "event:alpha:update", "alice"),
            Commit("ghi", datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc), "event:beta:init", "bob"),
        ]
        changes = [
            FileChange("abc", "agents/alpha/state.json", ChangeType.ADDED),
            FileChange("def", "agents/alpha/state.json", ChangeType.MODIFIED),
            FileChange("ghi", "agents/beta/state.json", ChangeType.ADDED),
        ]
        result = narrate(commits, changes)
        assert "3 commits" in result
        assert "agents/alpha/state.json" in result

    def test_empty_commits(self):
        result = narrate([], [])
        assert "No activity" in result

    def test_event_types_extracted(self):
        commits = [
            Commit("a", datetime(2026, 1, 1, tzinfo=timezone.utc), "event:alpha:beliefs_updated", "x"),
            Commit("b", datetime(2026, 1, 1, tzinfo=timezone.utc), "event:alpha:beliefs_updated", "x"),
            Commit("c", datetime(2026, 1, 1, tzinfo=timezone.utc), "event:alpha:state_changed", "x"),
        ]
        result = narrate(commits, [])
        assert "beliefs_updated" in result
        assert "state_changed" in result

    def test_multiple_contributors(self):
        commits = [
            Commit("a", datetime(2026, 1, 1, tzinfo=timezone.utc), "msg1", "alice"),
            Commit("b", datetime(2026, 1, 1, tzinfo=timezone.utc), "msg2", "bob"),
        ]
        result = narrate(commits, [])
        assert "alice" in result
        assert "bob" in result
