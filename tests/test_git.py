"""Tests for the Git operations layer."""

import subprocess
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from gitledger.git import Git, GitError, _CatFileReader, _parse_commit_block, _parse_iso, _parse_status_line
from gitledger.models import ChangeType


class TestParseIso:
    def test_z_suffix(self):
        dt = _parse_iso("2026-03-08T18:48:59Z")
        assert dt.tzinfo is not None
        assert dt.year == 2026

    def test_offset_suffix(self):
        dt = _parse_iso("2026-03-08T18:48:59+00:00")
        assert dt.year == 2026

    def test_no_tz(self):
        dt = _parse_iso("2026-03-08T18:48:59")
        assert dt.year == 2026


class TestParseStatusLine:
    def test_added(self):
        fc = _parse_status_line("A\tpath/to/file.json", "abc123")
        assert fc is not None
        assert fc.change_type == ChangeType.ADDED
        assert fc.path == "path/to/file.json"

    def test_modified(self):
        fc = _parse_status_line("M\tfile.json", "abc")
        assert fc is not None
        assert fc.change_type == ChangeType.MODIFIED

    def test_deleted(self):
        fc = _parse_status_line("D\tfile.json", "abc")
        assert fc is not None
        assert fc.change_type == ChangeType.DELETED

    def test_renamed(self):
        fc = _parse_status_line("R100\told.json\tnew.json", "abc")
        assert fc is not None
        assert fc.change_type == ChangeType.RENAMED
        assert fc.path == "new.json"

    def test_short_line(self):
        fc = _parse_status_line("A", "abc")
        assert fc is None


class TestParseCommitBlock:
    def test_valid_block(self):
        block = (
            "a" * 40 + "\n"
            "2026-01-01T00:00:00+00:00\n"
            "alice\n"
            "event:agent:init\n"
            '{"agent_id": "alpha"}'
        )
        commit = _parse_commit_block(block)
        assert commit is not None
        assert commit.author == "alice"
        assert commit.metadata == {"agent_id": "alpha"}

    def test_short_block(self):
        assert _parse_commit_block("too\nshort") is None

    def test_bad_hash(self):
        block = "short\n2026-01-01T00:00:00+00:00\nalice\nmsg"
        assert _parse_commit_block(block) is None

    def test_invalid_metadata_json(self):
        block = (
            "a" * 40 + "\n"
            "2026-01-01T00:00:00+00:00\n"
            "alice\n"
            "event:agent:init\n"
            "not-valid-json{{"
        )
        commit = _parse_commit_block(block)
        assert commit is not None
        assert commit.metadata == {}

    def test_checkpoint_message(self):
        block = (
            "a" * 40 + "\n"
            "2026-01-01T00:00:00+00:00\n"
            "alice\n"
            "checkpoint:20260101T000000"
        )
        commit = _parse_commit_block(block)
        assert commit is not None
        assert commit.is_checkpoint is True


class TestGitInit:
    def test_not_a_repo(self, tmp_path):
        with pytest.raises(GitError, match="not a git repository"):
            Git(tmp_path / "nonexistent")

    def test_init_and_open(self, tmp_path):
        git = Git.init(tmp_path / "new-repo")
        assert git.path.exists()
        git2 = Git(tmp_path / "new-repo")
        assert git2.path == git.path


class TestGitOperations:
    @pytest.fixture
    def git(self, tmp_path):
        g = Git.init(tmp_path / "repo")
        (g.path / "file.json").write_text('{"v": 1}')
        g.add("file.json")
        g.commit("event:test:init", '{"agent_id": "test"}')
        return g

    def test_log(self, git):
        commits = git.log()
        assert len(commits) == 1
        assert "init" in commits[0].message

    def test_log_with_path(self, git):
        commits = git.log(path="file.json")
        assert len(commits) == 1

    def test_log_with_since(self, git):
        since = datetime(2020, 1, 1, tzinfo=timezone.utc)
        commits = git.log(since=since)
        assert len(commits) == 1

    def test_log_with_until(self, git):
        until = datetime(2099, 1, 1, tzinfo=timezone.utc)
        commits = git.log(until=until)
        assert len(commits) == 1

    def test_log_with_max_count(self, git):
        commits = git.log(max_count=1)
        assert len(commits) == 1

    def test_log_with_grep(self, git):
        commits = git.log(grep="init")
        assert len(commits) == 1
        empty = git.log(grep="zzz_never")
        assert len(empty) == 0

    def test_log_empty(self, tmp_path):
        g = Git.init(tmp_path / "empty-repo")
        commits = g.log()
        assert commits == []

    def test_show(self, git):
        commits = git.log()
        content = git.show(commits[0].hash, "file.json")
        assert content is not None
        assert '"v": 1' in content

    def test_show_missing(self, git):
        commits = git.log()
        content = git.show(commits[0].hash, "nonexistent.json")
        assert content is None

    def test_show_many(self, git):
        commits = git.log()
        refs = [f"{commits[0].hash}:file.json"]
        results = git.show_many(refs)
        assert len(results) == 1
        assert results[0] is not None

    def test_show_commit(self, git):
        commits = git.log()
        commit = git.show_commit(commits[0].hash)
        assert commit is not None
        assert commit.hash == commits[0].hash

    def test_show_commit_bad_hash(self, git):
        result = git.show_commit("0" * 40)
        assert result is None

    def test_diff_names(self, git):
        (git.path / "file.json").write_text('{"v": 2}')
        git.add("file.json")
        git.commit("event:test:update", "")
        commits = git.log()
        changes = git.diff_names(commits[1].hash, commits[0].hash)
        assert len(changes) >= 1

    def test_diff_names_empty(self, git):
        changes = git.diff_names(git.log()[0].hash, git.log()[0].hash)
        assert changes == []

    def test_rev_parse(self, git):
        h = git.rev_parse("HEAD")
        assert len(h) == 40

    def test_list_files_with_commit(self, git):
        commits = git.log()
        files = git.list_files(commits[0].hash)
        assert "file.json" in files

    def test_list_files_without_commit(self, git):
        files = git.list_files()
        assert "file.json" in files

    def test_snapshot_contents(self, git):
        snap = git.snapshot_contents("HEAD")
        assert "file.json" in snap

    def test_snapshot_contents_empty(self, tmp_path):
        g = Git.init(tmp_path / "empty-repo")
        snap = g.snapshot_contents("HEAD")
        assert snap == {}

    def test_close(self, git):
        git.show(git.log()[0].hash, "file.json")
        git.close()

    def test_tag(self, git):
        git.tag("v1.0.0")
        output = subprocess.run(
            ["git", "tag"], cwd=git.path, capture_output=True, text=True,
        )
        assert "v1.0.0" in output.stdout


class TestCatFileReader:
    def test_read_missing_object(self, tmp_path):
        g = Git.init(tmp_path / "repo")
        (g.path / "f.txt").write_text("hello")
        g.add("f.txt")
        g.commit("init", "")
        reader = _CatFileReader(g.path)
        result = reader.read("0" * 40)
        assert result is None
        reader.close()

    def test_read_text(self, tmp_path):
        g = Git.init(tmp_path / "repo")
        (g.path / "f.txt").write_text("hello")
        g.add("f.txt")
        g.commit("init", "")
        commits = g.log()
        reader = _CatFileReader(g.path)
        text = reader.read_text(f"{commits[0].hash}:f.txt")
        assert text == "hello"
        reader.close()

    def test_read_text_missing(self, tmp_path):
        g = Git.init(tmp_path / "repo")
        (g.path / "f.txt").write_text("hello")
        g.add("f.txt")
        g.commit("init", "")
        reader = _CatFileReader(g.path)
        text = reader.read_text("0" * 40)
        assert text is None
        reader.close()

    def test_read_many(self, tmp_path):
        g = Git.init(tmp_path / "repo")
        (g.path / "a.txt").write_text("aaa")
        (g.path / "b.txt").write_text("bbb")
        g.add("a.txt")
        g.add("b.txt")
        g.commit("init", "")
        commits = g.log()
        reader = _CatFileReader(g.path)
        results = reader.read_many([
            f"{commits[0].hash}:a.txt",
            f"{commits[0].hash}:b.txt",
        ])
        assert len(results) == 2
        assert results[0] == b"aaa"
        assert results[1] == b"bbb"
        reader.close()

    def test_kill(self, tmp_path):
        g = Git.init(tmp_path / "repo")
        (g.path / "f.txt").write_text("hello")
        g.add("f.txt")
        g.commit("init", "")
        reader = _CatFileReader(g.path)
        reader._ensure()
        assert reader._proc is not None
        reader._kill()
        assert reader._proc is None

    def test_close_without_proc(self, tmp_path):
        g = Git.init(tmp_path / "repo")
        reader = _CatFileReader(g.path)
        reader.close()

    def test_broken_pipe_recovery_read(self, tmp_path):
        g = Git.init(tmp_path / "repo")
        (g.path / "f.txt").write_text("hello")
        g.add("f.txt")
        g.commit("init", "")
        commits = g.log()
        reader = _CatFileReader(g.path)
        reader._ensure()
        reader._proc.kill()
        reader._proc.wait()
        text = reader.read_text(f"{commits[0].hash}:f.txt")
        assert text == "hello"
        reader.close()

    def test_broken_pipe_recovery_read_many(self, tmp_path):
        g = Git.init(tmp_path / "repo")
        (g.path / "f.txt").write_text("hello")
        g.add("f.txt")
        g.commit("init", "")
        commits = g.log()
        reader = _CatFileReader(g.path)
        reader._ensure()
        reader._proc.kill()
        reader._proc.wait()
        results = reader.read_many([f"{commits[0].hash}:f.txt"])
        assert len(results) == 1
        assert results[0] == b"hello"
        reader.close()

    def test_read_recovers_from_broken_pipe(self, tmp_path):
        from unittest.mock import patch, MagicMock
        g = Git.init(tmp_path / "repo")
        (g.path / "f.txt").write_text("data")
        g.add("f.txt")
        g.commit("init", "")
        commits = g.log()
        reader = _CatFileReader(g.path)
        ref = f"{commits[0].hash}:f.txt"

        call_count = [0]
        original_ensure = _CatFileReader._ensure

        def flaky_ensure(self):
            call_count[0] += 1
            proc = original_ensure(self)
            if call_count[0] == 1:
                bad_proc = MagicMock()
                bad_proc.stdin = MagicMock()
                bad_proc.stdin.write = MagicMock(side_effect=BrokenPipeError("broken"))
                return bad_proc
            return proc

        with patch.object(_CatFileReader, "_ensure", flaky_ensure):
            result = reader.read(ref)
        assert result == b"data"
        reader.close()

    def test_read_chunk_recovers_from_broken_pipe(self, tmp_path):
        from unittest.mock import patch
        g = Git.init(tmp_path / "repo")
        (g.path / "f.txt").write_text("data")
        g.add("f.txt")
        g.commit("init", "")
        commits = g.log()
        reader = _CatFileReader(g.path)
        ref = f"{commits[0].hash}:f.txt"

        call_count = [0]
        original_do_read = _CatFileReader._do_read_chunk

        def flaky_do_read(self, oids):
            call_count[0] += 1
            if call_count[0] == 1:
                raise BrokenPipeError("broken")
            return original_do_read(self, oids)

        with patch.object(_CatFileReader, "_do_read_chunk", flaky_do_read):
            results = reader._read_chunk([ref])
        assert len(results) == 1
        assert results[0] == b"data"
        reader.close()

    def test_kill_handles_already_dead_process(self, tmp_path):
        g = Git.init(tmp_path / "repo")
        reader = _CatFileReader(g.path)
        reader._ensure()
        proc = reader._proc
        proc.kill()
        proc.wait()
        reader._kill()
        assert reader._proc is None

    def test_kill_handles_kill_exception(self, tmp_path):
        from unittest.mock import patch, MagicMock
        g = Git.init(tmp_path / "repo")
        reader = _CatFileReader(g.path)
        mock_proc = MagicMock()
        mock_proc.kill.side_effect = OSError("process already gone")
        reader._proc = mock_proc
        reader._kill()
        assert reader._proc is None

    def test_close_stdin_close_exception(self, tmp_path):
        from unittest.mock import MagicMock
        g = Git.init(tmp_path / "repo")
        reader = _CatFileReader(g.path)
        reader._ensure()
        original_close = reader._proc.stdin.close
        reader._proc.stdin.close = MagicMock(side_effect=OSError("stdin broken"))
        reader.close()
        assert reader._proc is None

    def test_close_stdin_already_closed(self, tmp_path):
        g = Git.init(tmp_path / "repo")
        reader = _CatFileReader(g.path)
        reader._ensure()
        reader._proc.stdin.close()
        reader.close()
        assert reader._proc is None

    def test_close_wait_timeout_kills(self, tmp_path):
        g = Git.init(tmp_path / "repo")
        reader = _CatFileReader(g.path)
        reader._ensure()

        original_wait = reader._proc.wait
        def slow_wait(timeout=None):
            raise subprocess.TimeoutExpired(cmd="git", timeout=2)
        reader._proc.wait = slow_wait
        reader.close()
        assert reader._proc is None
