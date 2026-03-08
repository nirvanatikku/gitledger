"""Tests for the SQLite index."""

import json
from datetime import datetime, timezone

from gitledger.index import Index, _flatten_json
from gitledger.models import ChangeType, Commit, FileChange


class TestFlattenJson:
    def test_flat_dict(self):
        result = _flatten_json({"a": 1, "b": "hello"})
        assert ("a", 1) in result
        assert ("b", "hello") in result

    def test_nested_dict(self):
        result = _flatten_json({"config": {"retry": 3}})
        assert ("config.retry", 3) in result

    def test_list(self):
        result = _flatten_json({"items": [1, 2]})
        assert ("items[0]", 1) in result
        assert ("items[1]", 2) in result

    def test_scalar(self):
        result = _flatten_json(42)
        assert result == [("", 42)]


class TestIndex:
    def test_index_and_query(self, tmp_path):
        idx = Index(tmp_path / "test.db")
        commit = Commit(
            hash="abc123",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            author="test",
            message="event:agent:init",
            metadata={},
        )
        changes = [
            FileChange("abc123", "state.json", ChangeType.ADDED),
        ]
        contents = {
            "state.json": json.dumps({"score": 0.85, "status": "active"}),
        }
        idx.index_commit(commit, changes, contents)

        timeline = idx.query_timeline("state.json")
        assert len(timeline) == 1
        assert timeline[0].hash == "abc123"

        trend = idx.query_trend("state.json", "score")
        assert len(trend) == 1
        assert trend[0][2] == 0.85

        idx.close()

    def test_idempotent_indexing(self, tmp_path):
        idx = Index(tmp_path / "test.db")
        commit = Commit(
            hash="abc123",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            author="test",
            message="msg",
            metadata={},
        )
        idx.index_commit(commit, [], {})
        idx.index_commit(commit, [], {})
        assert idx.has_commit("abc123")
        idx.close()

    def test_most_changed(self, tmp_path):
        idx = Index(tmp_path / "test.db")
        for i in range(5):
            commit = Commit(
                hash=f"hash{i}",
                timestamp=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
                author="test",
                message=f"commit {i}",
                metadata={},
            )
            changes = [FileChange(f"hash{i}", "hot.json", ChangeType.MODIFIED)]
            idx.index_commit(commit, changes, {})

        top = idx.most_changed_paths(limit=3)
        assert top[0] == ("hot.json", 5)
        idx.close()
