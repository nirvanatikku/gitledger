"""Tests for the SQLite index."""

import json
from datetime import datetime, timedelta, timezone

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


def _make_commit(hash_="abc123", hours=0, msg="event:agent:init", meta=None):
    return Commit(
        hash=hash_,
        timestamp=datetime(2026, 1, 1, hours, tzinfo=timezone.utc),
        author="test",
        message=msg,
        metadata=meta or {},
    )


class TestIndex:
    def test_index_and_query(self, tmp_path):
        idx = Index(tmp_path / "test.db")
        commit = _make_commit()
        changes = [FileChange("abc123", "state.json", ChangeType.ADDED)]
        contents = {"state.json": json.dumps({"score": 0.85, "status": "active"})}
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
        commit = _make_commit()
        idx.index_commit(commit, [], {})
        idx.index_commit(commit, [], {})
        assert idx.has_commit("abc123")
        idx.close()

    def test_most_changed(self, tmp_path):
        idx = Index(tmp_path / "test.db")
        for i in range(5):
            commit = _make_commit(hash_=f"hash{i}", hours=i)
            changes = [FileChange(f"hash{i}", "hot.json", ChangeType.MODIFIED)]
            idx.index_commit(commit, changes, {})

        top = idx.most_changed_paths(limit=3)
        assert top[0] == ("hot.json", 5)
        idx.close()

    def test_non_json_content_skipped(self, tmp_path):
        idx = Index(tmp_path / "test.db")
        commit = _make_commit()
        changes = [FileChange("abc123", "readme.txt", ChangeType.ADDED)]
        contents = {"readme.txt": "not json at all"}
        idx.index_commit(commit, changes, contents)

        values = idx.query_field_values("readme.txt", "anything")
        assert values == []
        idx.close()

    def test_none_content_skipped(self, tmp_path):
        idx = Index(tmp_path / "test.db")
        commit = _make_commit()
        changes = [FileChange("abc123", "missing.json", ChangeType.ADDED)]
        contents = {"missing.json": None}
        idx.index_commit(commit, changes, contents)

        values = idx.query_field_values("missing.json", "anything")
        assert values == []
        idx.close()

    def test_query_timeline_with_since(self, tmp_path):
        idx = Index(tmp_path / "test.db")
        c1 = _make_commit(hash_="h1", hours=8)
        c2 = _make_commit(hash_="h2", hours=14)
        idx.index_commit(c1, [FileChange("h1", "f.json", ChangeType.ADDED)], {})
        idx.index_commit(c2, [FileChange("h2", "f.json", ChangeType.MODIFIED)], {})

        since = datetime(2026, 1, 1, 10, tzinfo=timezone.utc)
        result = idx.query_timeline("f.json", since=since)
        assert len(result) == 1
        assert result[0].hash == "h2"
        idx.close()

    def test_query_timeline_with_until(self, tmp_path):
        idx = Index(tmp_path / "test.db")
        c1 = _make_commit(hash_="h1", hours=8)
        c2 = _make_commit(hash_="h2", hours=14)
        idx.index_commit(c1, [FileChange("h1", "f.json", ChangeType.ADDED)], {})
        idx.index_commit(c2, [FileChange("h2", "f.json", ChangeType.MODIFIED)], {})

        until = datetime(2026, 1, 1, 10, tzinfo=timezone.utc)
        result = idx.query_timeline("f.json", until=until)
        assert len(result) == 1
        assert result[0].hash == "h1"
        idx.close()

    def test_query_trend_with_since_until(self, tmp_path):
        idx = Index(tmp_path / "test.db")
        for i in range(5):
            c = _make_commit(hash_=f"h{i}", hours=i * 3)
            idx.index_commit(
                c,
                [FileChange(f"h{i}", "f.json", ChangeType.MODIFIED)],
                {"f.json": json.dumps({"val": i * 10})},
            )

        since = datetime(2026, 1, 1, 4, tzinfo=timezone.utc)
        until = datetime(2026, 1, 1, 10, tzinfo=timezone.utc)
        result = idx.query_trend("f.json", "val", since=since, until=until)
        assert len(result) == 2
        idx.close()

    def test_query_field_values(self, tmp_path):
        idx = Index(tmp_path / "test.db")
        c1 = _make_commit(hash_="h1", hours=0)
        c2 = _make_commit(hash_="h2", hours=1)
        idx.index_commit(
            c1,
            [FileChange("h1", "state.json", ChangeType.ADDED)],
            {"state.json": json.dumps({"score": 0.5})},
        )
        idx.index_commit(
            c2,
            [FileChange("h2", "state.json", ChangeType.MODIFIED)],
            {"state.json": json.dumps({"score": 0.9})},
        )

        values = idx.query_field_values("state.json", "score")
        assert len(values) == 2
        assert values[0].value == "0.5"
        assert values[1].value == "0.9"
        idx.close()

    def test_query_commits_by_hashes(self, tmp_path):
        idx = Index(tmp_path / "test.db")
        c1 = _make_commit(hash_="h1", hours=0)
        c2 = _make_commit(hash_="h2", hours=1)
        c3 = _make_commit(hash_="h3", hours=2)
        idx.index_commit(c1, [], {})
        idx.index_commit(c2, [], {})
        idx.index_commit(c3, [], {})

        result = idx.query_commits_by_hashes({"h1", "h3"})
        assert len(result) == 2
        hashes = {c.hash for c in result}
        assert hashes == {"h1", "h3"}
        idx.close()

    def test_query_commits_by_hashes_empty(self, tmp_path):
        idx = Index(tmp_path / "test.db")
        result = idx.query_commits_by_hashes(set())
        assert result == []
        idx.close()

    def test_query_changes_by_path_pattern_with_since_until(self, tmp_path):
        idx = Index(tmp_path / "test.db")
        c1 = _make_commit(hash_="h1", hours=2)
        c2 = _make_commit(hash_="h2", hours=8)
        c3 = _make_commit(hash_="h3", hours=14)
        idx.index_commit(c1, [FileChange("h1", "agents/a.json", ChangeType.ADDED)], {})
        idx.index_commit(c2, [FileChange("h2", "agents/b.json", ChangeType.ADDED)], {})
        idx.index_commit(c3, [FileChange("h3", "agents/c.json", ChangeType.ADDED)], {})

        since = datetime(2026, 1, 1, 5, tzinfo=timezone.utc)
        until = datetime(2026, 1, 1, 10, tzinfo=timezone.utc)
        result = idx.query_changes_by_path_pattern("agents/*", since=since, until=until)
        assert len(result) == 1
        assert result[0].path == "agents/b.json"
        idx.close()

    def test_rebuild(self, tmp_path):
        idx = Index(tmp_path / "test.db")
        c = _make_commit()
        idx.index_commit(c, [FileChange("abc123", "f.json", ChangeType.ADDED)], {})
        assert idx.has_commit("abc123")

        idx.rebuild()
        assert not idx.has_commit("abc123")
        idx.close()

    def test_row_to_commit_with_metadata(self, tmp_path):
        idx = Index(tmp_path / "test.db")
        c = _make_commit(meta={"custom": "data"})
        idx.index_commit(c, [], {})

        result = idx.query_commits_by_hashes({"abc123"})
        assert len(result) == 1
        assert result[0].metadata == {"custom": "data"}
        idx.close()

    def test_row_to_commit_bad_metadata_json(self, tmp_path):
        idx = Index(tmp_path / "test.db")
        c = _make_commit()
        idx.index_commit(c, [], {})

        idx._conn.execute(
            "UPDATE commits SET metadata_json = ? WHERE hash = ?",
            ("not-valid-json{{{", "abc123"),
        )
        idx._conn.commit()

        result = idx.query_commits_by_hashes({"abc123"})
        assert len(result) == 1
        assert result[0].metadata == {}
        idx.close()
