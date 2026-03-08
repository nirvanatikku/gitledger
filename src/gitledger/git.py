"""High-performance Git operations via subprocess.

Architecture
~~~~~~~~~~~~
* Write-path operations (add, commit, tag, init) use one-shot ``subprocess.run``.
* Read-path operations use a persistent long-running ``git cat-file --batch``
  process for streaming object reads.  The reader auto-restarts on broken pipe
  and chunks large batches to avoid pipe buffer deadlocks.
* ``log()`` supports ``--grep`` to push search filtering into git.
* ``snapshot_contents()`` replaces N+1 show() calls with list_files + show_many.

All public methods are safe to call from a single thread.  The long-running
process is lazily started on first read and cleaned up via ``close()``.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from gitledger.models import ChangeType, Commit, FileChange


def _parse_iso(s: str) -> datetime:
    """Parse an ISO-8601 string, handling the 'Z' suffix on Python 3.10."""
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


class GitError(Exception):
    pass


_STATUS_MAP = {
    "A": ChangeType.ADDED,
    "M": ChangeType.MODIFIED,
    "D": ChangeType.DELETED,
    "R": ChangeType.RENAMED,
    "C": ChangeType.ADDED,
    "T": ChangeType.MODIFIED,
}

_READ_CHUNK = 200


class _CatFileReader:
    """Persistent ``git cat-file --batch`` process for streaming reads.

    Auto-restarts if the underlying process dies (e.g., repo GC, broken pipe).
    Chunks large batches to stay within OS pipe buffer limits.
    """

    __slots__ = ("_proc", "_repo_path")

    def __init__(self, repo_path: Path) -> None:
        self._repo_path = repo_path
        self._proc: subprocess.Popen | None = None

    def _ensure(self) -> subprocess.Popen:
        if self._proc is None or self._proc.poll() is not None:
            self._proc = subprocess.Popen(
                ["git", "cat-file", "--batch"],
                cwd=self._repo_path,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        return self._proc

    def _read_one(self, proc: subprocess.Popen) -> bytes | None:
        assert proc.stdout is not None
        header = proc.stdout.readline()
        if not header or header.rstrip().endswith(b"missing"):
            return None
        parts = header.split()
        size = int(parts[2])
        data = proc.stdout.read(size)
        proc.stdout.read(1)
        return data

    def read(self, object_id: str) -> bytes | None:
        try:
            proc = self._ensure()
            assert proc.stdin is not None
            proc.stdin.write(f"{object_id}\n".encode())
            proc.stdin.flush()
            return self._read_one(proc)
        except (BrokenPipeError, OSError):
            self._kill()
            proc = self._ensure()
            assert proc.stdin is not None
            proc.stdin.write(f"{object_id}\n".encode())
            proc.stdin.flush()
            return self._read_one(proc)

    def read_text(self, object_id: str) -> str | None:
        raw = self.read(object_id)
        return raw.decode("utf-8", errors="replace") if raw is not None else None

    def read_many(self, object_ids: list[str]) -> list[bytes | None]:
        results: list[bytes | None] = []
        for start in range(0, len(object_ids), _READ_CHUNK):
            chunk = object_ids[start : start + _READ_CHUNK]
            results.extend(self._read_chunk(chunk))
        return results

    def _read_chunk(self, object_ids: list[str]) -> list[bytes | None]:
        try:
            return self._do_read_chunk(object_ids)
        except (BrokenPipeError, OSError):
            self._kill()
            return self._do_read_chunk(object_ids)

    def _do_read_chunk(self, object_ids: list[str]) -> list[bytes | None]:
        proc = self._ensure()
        assert proc.stdin is not None
        payload = "".join(f"{oid}\n" for oid in object_ids).encode()
        proc.stdin.write(payload)
        proc.stdin.flush()
        return [self._read_one(proc) for _ in object_ids]

    def _kill(self) -> None:
        if self._proc is not None:
            try:
                self._proc.kill()
            except Exception:
                pass
            self._proc = None

    def close(self) -> None:
        if self._proc is not None:
            if self._proc.stdin:
                try:
                    self._proc.stdin.close()
                except Exception:
                    pass
            try:
                self._proc.wait(timeout=2)
            except Exception:
                self._proc.kill()
            self._proc = None


def _parse_status_line(line: str, commit_hash: str) -> FileChange | None:
    """Parse a name-status line, handling renames/copies (e.g., R100, C100)."""
    parts = line.split("\t")
    if len(parts) < 2:
        return None
    status_char = parts[0][0]
    change_type = _STATUS_MAP.get(status_char, ChangeType.MODIFIED)
    path = parts[-1]
    return FileChange(
        commit_hash=commit_hash,
        path=path,
        change_type=change_type,
    )


def _parse_commit_block(raw: str) -> Commit | None:
    """Parse a single commit block from --format output."""
    lines = raw.split("\n")
    if len(lines) < 4:
        return None
    hash_ = lines[0]
    if len(hash_) != 40:
        return None
    timestamp = _parse_iso(lines[1])
    author = lines[2]
    message = lines[3]
    body = "\n".join(lines[4:]).strip()

    metadata: dict = {}
    is_checkpoint = message.startswith("checkpoint:")
    if body:
        try:
            metadata = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            pass

    return Commit(
        hash=hash_,
        timestamp=timestamp,
        message=message,
        author=author,
        metadata=metadata,
        is_checkpoint=is_checkpoint,
    )


class Git:
    """High-performance wrapper around the git CLI."""

    __slots__ = ("path", "_reader")

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        if not (self.path / ".git").exists():
            raise GitError(f"not a git repository: {self.path}")
        self._reader: _CatFileReader | None = None

    def _get_reader(self) -> _CatFileReader:
        if self._reader is None:
            self._reader = _CatFileReader(self.path)
        return self._reader

    def close(self) -> None:
        if self._reader is not None:
            self._reader.close()
            self._reader = None

    def _run(self, *args: str, check: bool = True) -> str:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.path,
                capture_output=True,
                text=True,
                check=check,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as exc:
            raise GitError(exc.stderr.strip()) from exc

    @classmethod
    def init(cls, path: str | Path) -> "Git":
        path = Path(path).resolve()
        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "init"],
            cwd=path, capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "gitledger@localhost"],
            cwd=path, capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "GitLedger"],
            cwd=path, capture_output=True, text=True, check=True,
        )
        return cls(path)

    def add(self, *paths: str) -> None:
        self._run("add", *paths)

    def commit(self, message: str, body: str | None = None) -> str:
        args = ["commit", "--allow-empty", "-m", message]
        if body:
            args.extend(["-m", body])
        self._run(*args)
        return self._run("rev-parse", "HEAD")

    def tag(self, name: str, message: str | None = None) -> None:
        args = ["tag"]
        if message:
            args.extend(["-a", "-m", message])
        args.append(name)
        self._run(*args)

    def log(
        self,
        path: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        max_count: int | None = None,
        grep: str | None = None,
    ) -> list[Commit]:
        fmt = "%H%n%aI%n%an%n%s%n%b%n---END---"
        args = ["log", f"--format={fmt}"]
        if since:
            args.append(f"--since={since.isoformat()}")
        if until:
            args.append(f"--until={until.isoformat()}")
        if max_count:
            args.append(f"--max-count={max_count}")
        if grep:
            args.extend([f"--grep={grep}", "-i"])
        args.append("--")
        if path:
            args.append(path)

        output = self._run(*args, check=False)
        if not output:
            return []

        commits: list[Commit] = []
        for block in output.split("---END---"):
            commit = _parse_commit_block(block.strip())
            if commit is not None:
                commits.append(commit)
        return commits

    def diff_names(self, commit_a: str, commit_b: str) -> list[FileChange]:
        output = self._run(
            "diff", "--name-status", commit_a, commit_b, check=False,
        )
        if not output:
            return []

        changes: list[FileChange] = []
        for line in output.split("\n"):
            fc = _parse_status_line(line.strip(), commit_b)
            if fc:
                changes.append(fc)
        return changes

    def show(self, commit: str, path: str) -> str | None:
        return self._get_reader().read_text(f"{commit}:{path}")

    def show_many(self, refs: list[str]) -> list[str | None]:
        raw = self._get_reader().read_many(refs)
        return [
            b.decode("utf-8", errors="replace") if b is not None else None
            for b in raw
        ]

    def rev_parse(self, ref: str) -> str:
        return self._run("rev-parse", ref)

    def show_commit(self, commit_hash: str) -> Commit | None:
        fmt = "%H%n%aI%n%an%n%s%n%b"
        output = self._run(
            "log", "-1", f"--format={fmt}", commit_hash, check=False,
        )
        if not output:
            return None
        return _parse_commit_block(output)

    def list_files(self, commit: str | None = None) -> list[str]:
        if commit:
            output = self._run("ls-tree", "-r", "--name-only", commit, check=False)
        else:
            output = self._run("ls-files", check=False)
        if not output:
            return []
        return output.split("\n")

    def snapshot_contents(self, commit: str = "HEAD") -> dict[str, str]:
        """Return all file contents at a commit in a single batched read."""
        files = self.list_files(commit)
        if not files:
            return {}
        refs = [f"{commit}:{f}" for f in files]
        contents = self.show_many(refs)
        return {
            f: content
            for f, content in zip(files, contents)
            if content is not None
        }
