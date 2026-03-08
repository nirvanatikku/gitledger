"""Tests for the core Repo API."""

import json

from gitledger import Repo


class TestRepoInit:
    def test_init_creates_repo(self, tmp_path):
        repo = Repo.init(tmp_path / "new-repo")
        assert (tmp_path / "new-repo" / ".git").exists()
        repo.close()

    def test_init_creates_index(self, tmp_path):
        repo = Repo.init(tmp_path / "new-repo")
        assert (tmp_path / "new-repo" / ".gitledger" / "index.db").exists()
        repo.close()

    def test_context_manager(self, tmp_path):
        with Repo.init(tmp_path / "ctx-repo") as repo:
            repo.write("test.json", {"key": "value"})
            repo.commit_event("test", "created", ["test.json"])


class TestWrite:
    def test_write_dict(self, tmp_repo):
        tmp_repo.write("data.json", {"key": "value"})
        content = (tmp_repo.path / "data.json").read_text()
        assert json.loads(content) == {"key": "value"}

    def test_write_string(self, tmp_repo):
        tmp_repo.write("readme.txt", "hello world")
        content = (tmp_repo.path / "readme.txt").read_text()
        assert content == "hello world"

    def test_write_nested_path(self, tmp_repo):
        tmp_repo.write("agents/alpha/state.json", {"status": "active"})
        assert (tmp_repo.path / "agents" / "alpha" / "state.json").exists()


class TestCommit:
    def test_event_commit(self, tmp_repo):
        tmp_repo.write("state.json", {"v": 1})
        hash_ = tmp_repo.commit_event("agent-1", "init", ["state.json"])
        assert len(hash_) == 40

    def test_checkpoint_commit(self, tmp_repo):
        tmp_repo.write("state.json", {"v": 1})
        tmp_repo.commit_event("agent-1", "init")
        hash_ = tmp_repo.commit_checkpoint()
        assert len(hash_) == 40


class TestTimeline:
    def test_timeline_returns_commits(self, populated_repo):
        timeline = populated_repo.timeline("agents/alpha/state.json")
        assert len(timeline) == 3

    def test_timeline_ordered(self, populated_repo):
        timeline = populated_repo.timeline("agents/alpha/state.json")
        timestamps = [c.timestamp for c in timeline]
        assert timestamps == sorted(timestamps)

    def test_timeline_empty_path(self, populated_repo):
        timeline = populated_repo.timeline("nonexistent.json")
        assert timeline == []


class TestDiff:
    def test_semantic_diff(self, populated_repo):
        timeline = populated_repo.timeline("agents/alpha/state.json")
        assert len(timeline) >= 2
        diffs = populated_repo.diff(
            "agents/alpha/state.json",
            timeline[0].hash,
            timeline[1].hash,
        )
        assert len(diffs) > 0
        fields = {d.field for d in diffs}
        assert "confidence_score" in fields or "tasks_completed" in fields

    def test_diff_shows_values(self, populated_repo):
        timeline = populated_repo.timeline("agents/alpha/state.json")
        diffs = populated_repo.diff(
            "agents/alpha/state.json",
            timeline[0].hash,
            timeline[1].hash,
        )
        score_diff = [d for d in diffs if d.field == "confidence_score"]
        if score_diff:
            assert score_diff[0].old_value == 0.85
            assert score_diff[0].new_value == 0.90


class TestTrend:
    def test_trend_extraction(self, populated_repo):
        trend = populated_repo.trend(
            "agents/alpha/state.json",
            "confidence_score",
        )
        assert len(trend) == 3
        values = [p.value for p in trend]
        assert values == [0.85, 0.90, 0.72]


class TestSnapshot:
    def test_snapshot_head(self, populated_repo):
        snap = populated_repo.snapshot()
        assert "agents/alpha/state.json" in snap
        assert "agents/beta/state.json" in snap


class TestSearch:
    def test_search_by_message(self, populated_repo):
        results = populated_repo.search("beliefs_updated")
        assert len(results) >= 1
        assert any("beliefs_updated" in c.message for c in results)


class TestCorrelate:
    def test_no_correlation(self, populated_repo):
        results = populated_repo.correlate(
            "agents/alpha/state.json",
            "agents/beta/state.json",
        )
        assert results == []


class TestMostChanged:
    def test_most_changed(self, populated_repo):
        top = populated_repo.most_changed(limit=5)
        assert len(top) > 0
        paths = [p for p, _ in top]
        assert "agents/alpha/state.json" in paths

    def test_most_changed_with_pattern(self, populated_repo):
        top = populated_repo.most_changed(pattern="agents/alpha/*")
        assert all("agents/alpha" in p for p, _ in top)


class TestSync:
    def test_sync_returns_count(self, tmp_path):
        repo = Repo.init(tmp_path / "sync-repo")
        repo.write("a.json", {"v": 1})
        repo.commit_event("x", "init", ["a.json"])
        repo.close()

        repo2 = Repo(tmp_path / "sync-repo")
        count = repo2.sync()
        assert count >= 0
        repo2.close()
