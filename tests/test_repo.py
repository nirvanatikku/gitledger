"""Tests for the core Repo API."""

import json
from datetime import datetime, timedelta, timezone

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

    def test_event_commit_with_metadata(self, tmp_repo):
        tmp_repo.write("state.json", {"v": 1})
        hash_ = tmp_repo.commit_event(
            "agent-1", "init", ["state.json"],
            metadata={"priority": "high", "source": "test"},
        )
        assert len(hash_) == 40
        timeline = tmp_repo.timeline("state.json")
        assert len(timeline) == 1
        assert timeline[0].metadata.get("priority") == "high"


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

    def test_timeline_with_since_until(self, populated_repo):
        full = populated_repo.timeline("agents/alpha/state.json")
        assert len(full) >= 2
        mid = full[1].timestamp
        after = populated_repo.timeline("agents/alpha/state.json", since=mid)
        assert len(after) <= len(full)
        before = populated_repo.timeline("agents/alpha/state.json", until=mid)
        assert len(before) <= len(full)


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

    def test_snapshot_specific_commit(self, populated_repo):
        timeline = populated_repo.timeline("agents/alpha/state.json")
        snap = populated_repo.snapshot(timeline[0].hash)
        data = json.loads(snap["agents/alpha/state.json"])
        assert data["confidence_score"] == 0.85


class TestEpisodes:
    def test_episodes_basic(self, populated_repo):
        episodes = populated_repo.episodes("agents/alpha/*")
        assert len(episodes) >= 1
        assert len(episodes[0].commits) > 0

    def test_episodes_with_event_type(self, populated_repo):
        episodes = populated_repo.episodes("agents/alpha/*", event_type="state_updated")
        assert len(episodes) >= 1
        assert episodes[0].episode_type == "state_updated"

    def test_episodes_empty_result(self, populated_repo):
        episodes = populated_repo.episodes("nonexistent/*")
        assert episodes == []

    def test_episodes_event_type_no_match(self, populated_repo):
        episodes = populated_repo.episodes("agents/alpha/*", event_type="never_happened")
        assert episodes == []

    def test_episodes_with_window(self, populated_repo):
        episodes = populated_repo.episodes(
            "agents/alpha/*",
            window=timedelta(days=1),
        )
        assert len(episodes) >= 1


class TestDrift:
    def test_drift_basic(self, populated_repo):
        values = populated_repo.drift("agents/alpha/state.json")
        assert len(values) > 0
        fields = {v.json_path for v in values}
        assert "confidence_score" in fields or "status" in fields

    def test_drift_with_schema(self, populated_repo):
        values = populated_repo.drift(
            "agents/alpha/state.json",
            schema={"confidence_score": float},
        )
        for v in values:
            assert v.json_path == "confidence_score"

    def test_drift_empty_path(self, populated_repo):
        values = populated_repo.drift("nonexistent.json")
        assert values == []


class TestNarrate:
    def test_narrate(self, populated_repo):
        result = populated_repo.narrate("agents/*")
        assert "commit" in result


class TestAnomalies:
    def test_anomalies_basic(self, populated_repo):
        anomalies = populated_repo.anomalies(
            "agents/alpha/state.json",
            "confidence_score",
            sigma=0.5,
        )
        assert isinstance(anomalies, list)


class TestSearch:
    def test_search_by_message(self, populated_repo):
        results = populated_repo.search("beliefs_updated")
        assert len(results) >= 1
        assert any("beliefs_updated" in c.message for c in results)

    def test_search_with_path_filter(self, populated_repo):
        results = populated_repo.search("state", paths=["agents/alpha/*"])
        for r in results:
            assert "state" in r.message.lower() or "state" in str(r.metadata)

    def test_search_no_results(self, populated_repo):
        results = populated_repo.search("zzz_nonexistent_zzz")
        assert results == []


class TestCorrelate:
    def test_no_correlation(self, populated_repo):
        results = populated_repo.correlate(
            "agents/alpha/state.json",
            "agents/beta/state.json",
        )
        assert results == []

    def test_correlation_with_shared_commit(self, tmp_path):
        repo = Repo.init(tmp_path / "corr-repo")
        repo.write("a.json", {"v": 1})
        repo.write("b.json", {"v": 1})
        repo.commit_event("x", "init", ["a.json", "b.json"])
        results = repo.correlate("a.json", "b.json")
        assert len(results) >= 1
        repo.close()

    def test_correlate_with_window(self, tmp_path):
        repo = Repo.init(tmp_path / "corr-repo")
        repo.write("a.json", {"v": 1})
        repo.write("b.json", {"v": 1})
        repo.commit_event("x", "init", ["a.json", "b.json"])
        results = repo.correlate("a.json", "b.json", window=timedelta(days=1))
        assert len(results) >= 1
        repo.close()


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


class TestDriftEdgeCases:
    def test_drift_with_non_json_file(self, tmp_path):
        repo = Repo.init(tmp_path / "drift-repo")
        repo.write("readme.txt", "version 1")
        repo.commit_event("x", "init", ["readme.txt"])
        repo.write("readme.txt", "version 2")
        repo.commit_event("x", "update", ["readme.txt"])
        values = repo.drift("readme.txt")
        assert values == []
        repo.close()

    def test_drift_with_non_json_then_json(self, tmp_path):
        repo = Repo.init(tmp_path / "drift-repo")
        repo.write("data.json", {"score": 1})
        repo.commit_event("x", "init", ["data.json"])
        (repo.path / "data.json").write_text("not json anymore")
        repo._git.add("data.json")
        repo._git.commit("event:x:break", "")
        repo.sync()
        repo.write("data.json", {"score": 2})
        repo.commit_event("x", "fix", ["data.json"])
        values = repo.drift("data.json")
        assert isinstance(values, list)
        repo.close()

    def test_drift_with_none_content(self, tmp_path):
        from unittest.mock import patch
        repo = Repo.init(tmp_path / "drift-repo")
        repo.write("data.json", {"score": 1})
        repo.commit_event("x", "init", ["data.json"])
        repo.write("data.json", {"score": 2})
        repo.commit_event("x", "update", ["data.json"])

        original_show_many = repo._git.__class__.show_many
        def show_many_with_none(self_git, refs):
            results = original_show_many(self_git, refs)
            if len(results) >= 1:
                results[0] = None
            return results

        with patch.object(repo._git.__class__, "show_many", show_many_with_none):
            values = repo.drift("data.json")
        assert isinstance(values, list)
        repo.close()


class TestRebuildIndex:
    def test_rebuild_index(self, tmp_path):
        repo = Repo.init(tmp_path / "rebuild-repo")
        repo.write("a.json", {"v": 1})
        repo.commit_event("x", "init", ["a.json"])

        count = repo.rebuild_index()
        assert count >= 1

        timeline = repo.timeline("a.json")
        assert len(timeline) == 1
        repo.close()


class TestIndexCommitEdge:
    def test_index_commit_with_bad_hash(self, tmp_path):
        repo = Repo.init(tmp_path / "edge-repo")
        repo._index_commit("0" * 40)
        repo.close()
