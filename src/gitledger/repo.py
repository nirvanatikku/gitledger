"""Main Repo class — the public API surface of GitLedger."""

from __future__ import annotations

import fnmatch
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from gitledger.diff import semantic_diff
from gitledger.git import Git
from gitledger.index import Index
from gitledger.models import (
    Anomaly,
    Commit,
    DiffEntry,
    Episode,
    FieldValue,
    FileChange,
    TrendPoint,
)
from gitledger.narrative import narrate
from gitledger.trend import detect_anomalies, extract_trend


class Repo:
    """A git-native structural memory interface.

    Usage::

        repo = Repo("./memory")
        timeline = repo.timeline("agents/alpha/beliefs.json")
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        self._git = Git(self.path)
        self._index = Index(self.path / ".gitledger" / "index.db")

    @classmethod
    def init(cls, path: str | Path) -> "Repo":
        """Initialize a new GitLedger repository."""
        git = Git.init(path)
        return cls(git.path)

    def close(self) -> None:
        """Close the index database connection and git reader."""
        self._git.close()
        self._index.close()

    def __enter__(self) -> "Repo":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ── Write Operations ──────────────────────────────────────────────

    def write(self, path: str, content: str | dict | list) -> None:
        """Write an artifact to the repository (without committing)."""
        full_path = self.path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, (dict, list)):
            content = json.dumps(content, indent=2, default=str)
        full_path.write_text(content)
        self._git.add(path)

    def commit_event(
        self,
        entity: str,
        event_type: str,
        changed_paths: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create an event commit and index it."""
        message = f"event:{entity}:{event_type}"
        body_data = {
            "agent_id": entity,
            "event_type": event_type,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "changed_paths": changed_paths or [],
            "checkpoint": False,
        }
        if metadata:
            body_data.update(metadata)

        body = json.dumps(body_data)
        commit_hash = self._git.commit(message, body)
        self._index_commit(commit_hash)
        return commit_hash

    def commit_checkpoint(self, tag: str | None = None) -> str:
        """Create a checkpoint commit and optional tag."""
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
        message = f"checkpoint:{ts}"
        commit_hash = self._git.commit(message)

        if tag is None:
            tag = f"checkpoint-{ts}"
        self._git.tag(tag, message=f"Checkpoint at {ts}")

        self._index_commit(commit_hash)
        return commit_hash

    # ── Query Operations ──────────────────────────────────────────────

    def timeline(
        self,
        path: str,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[Commit]:
        """Return the commit timeline for a specific path."""
        return self._index.query_timeline(path, since, until)

    def diff(
        self,
        path: str,
        commit_a: str,
        commit_b: str,
    ) -> list[DiffEntry]:
        """Compute semantic diff for a path between two commits.

        Uses batched cat-file reads (2 objects in one round-trip).
        """
        refs = [f"{commit_a}:{path}", f"{commit_b}:{path}"]
        contents = self._git.show_many(refs)
        return semantic_diff(contents[0], contents[1], path)

    def trend(
        self,
        path: str,
        field: str,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[TrendPoint]:
        """Extract trend data for a numeric field across commits."""
        raw = self._index.query_trend(path, field, since, until)
        return extract_trend(raw)

    def episodes(
        self,
        path_pattern: str,
        event_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        window: timedelta | None = None,
    ) -> list[Episode]:
        """Group related commits into episodes."""
        if window and not since:
            anchor = until or datetime.now(tz=timezone.utc)
            since = anchor - window

        changes = self._index.query_changes_by_path_pattern(
            path_pattern, since, until,
        )
        if not changes:
            return []

        commit_hashes = list(dict.fromkeys(c.commit_hash for c in changes))

        if event_type:
            commit_set = set(commit_hashes)
            commits = self._index.query_commits_by_hashes(commit_set)
            commit_hashes = [
                c.hash for c in commits
                if event_type in c.message
            ]

        if not commit_hashes:
            return []

        return [Episode(
            id=uuid.uuid4().hex[:12],
            start_commit=commit_hashes[0],
            end_commit=commit_hashes[-1],
            path_pattern=path_pattern,
            episode_type=event_type or "all",
            commits=commit_hashes,
        )]

    def snapshot(self, commit: str | None = None) -> dict[str, str]:
        """Return all file contents at a given commit.

        Uses list_files + batched show_many (1 subprocess + 1 cat-file batch).
        """
        return self._git.snapshot_contents(commit or "HEAD")

    def drift(
        self,
        path: str,
        schema: dict[str, type] | None = None,
    ) -> list[FieldValue]:
        """Detect field value changes for a structured artifact.

        Uses batched show_many to read all versions in one round-trip.
        """
        commits = self._index.query_timeline(path)
        if not commits:
            return []

        refs = [f"{c.hash}:{path}" for c in commits]
        contents = self._git.show_many(refs)

        all_values: list[FieldValue] = []
        prev_data: dict | None = None

        for commit, content in zip(commits, contents):
            if content is None:
                continue
            try:
                data = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                continue

            if prev_data is not None:
                fields_to_check = schema.keys() if schema else set(data.keys()) | set(prev_data.keys())
                for field in fields_to_check:
                    old_val = prev_data.get(field)
                    new_val = data.get(field)
                    if old_val != new_val:
                        all_values.append(FieldValue(
                            commit_hash=commit.hash,
                            path=path,
                            json_path=field,
                            value=new_val,
                        ))

            prev_data = data

        return all_values

    def narrate(
        self,
        path_pattern: str = "*",
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> str:
        """Generate a narrative summary of repository activity."""
        commits = self._git.log(since=since, until=until)
        changes = self._index.query_changes_by_path_pattern(
            path_pattern, since, until,
        )
        return narrate(commits, changes, since, until)

    def anomalies(
        self,
        path: str,
        field: str,
        sigma: float = 2.0,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[Anomaly]:
        """Detect anomalies in a numeric field's trend."""
        points = self.trend(path, field, since, until)
        return detect_anomalies(points, path, field, sigma)

    def search(
        self,
        query: str,
        paths: list[str] | None = None,
    ) -> list[Commit]:
        """Search commit messages for a query string.

        Uses git --grep to push message filtering into git (single subprocess).
        Path filtering uses the SQLite index (no per-commit subprocess).
        """
        matching = self._git.log(grep=query)
        if not paths or not matching:
            return matching

        matching_hashes = {c.hash for c in matching}
        path_hashes: set[str] = set()
        for p in paths:
            changes = self._index.query_changes_by_path_pattern(p)
            path_hashes.update(c.commit_hash for c in changes)

        shared = matching_hashes & path_hashes
        return [c for c in matching if c.hash in shared]

    def correlate(
        self,
        path_a: str,
        path_b: str,
        since: datetime | None = None,
        until: datetime | None = None,
        window: timedelta | None = None,
    ) -> list[Commit]:
        """Find commits that changed both paths."""
        if window and not since:
            anchor = until or datetime.now(tz=timezone.utc)
            since = anchor - window

        timeline_a = {c.hash for c in self.timeline(path_a, since, until)}
        timeline_b = {c.hash for c in self.timeline(path_b, since, until)}
        shared = timeline_a & timeline_b
        if not shared:
            return []
        all_commits = self._git.log(since=since, until=until)
        return [c for c in all_commits if c.hash in shared]

    def most_changed(
        self,
        pattern: str | None = None,
        limit: int = 10,
    ) -> list[tuple[str, int]]:
        """Return the most frequently changed paths."""
        return self._index.most_changed_paths(pattern, limit)

    # ── Indexing ──────────────────────────────────────────────────────

    def sync(self) -> int:
        """Index all un-indexed commits. Returns count of newly indexed commits."""
        commits = self._git.log()
        count = 0
        for commit in reversed(commits):
            if not self._index.has_commit(commit.hash):
                self._index_commit(commit.hash)
                count += 1
        return count

    def rebuild_index(self) -> int:
        """Rebuild the entire index from scratch."""
        self._index.rebuild()
        return self.sync()

    def _index_commit(self, commit_hash: str) -> None:
        """Index a single commit.

        Uses show_commit (1 subprocess) + diff_names (1 subprocess)
        + show_many for file contents (batched through persistent cat-file).
        """
        commit = self._git.show_commit(commit_hash)
        if commit is None:
            return

        try:
            parent = self._git.rev_parse(f"{commit_hash}^")
            changes = self._git.diff_names(parent, commit_hash)
        except Exception:
            files = self._git.list_files(commit_hash)
            from gitledger.models import ChangeType as CT
            changes = [
                FileChange(commit_hash=commit_hash, path=f, change_type=CT.ADDED)
                for f in files
            ]

        if changes:
            refs = [f"{commit_hash}:{c.path}" for c in changes]
            contents = self._git.show_many(refs)
            file_contents: dict[str, str | None] = {
                change.path: content
                for change, content in zip(changes, contents)
            }
        else:
            file_contents = {}

        self._index.index_commit(commit, changes, file_contents)
