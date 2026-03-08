"""SQLite sidecar index for fast temporal queries."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from gitledger.models import (
    Anomaly,
    ChangeType,
    Commit,
    FieldValue,
    FileChange,
)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS commits (
    hash TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    author TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata_json TEXT,
    is_checkpoint INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS file_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    commit_hash TEXT NOT NULL,
    path TEXT NOT NULL,
    change_type TEXT NOT NULL,
    old_hash TEXT,
    new_hash TEXT,
    FOREIGN KEY (commit_hash) REFERENCES commits(hash)
);

CREATE TABLE IF NOT EXISTS field_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    commit_hash TEXT NOT NULL,
    path TEXT NOT NULL,
    json_path TEXT NOT NULL,
    value_text TEXT,
    value_numeric REAL,
    FOREIGN KEY (commit_hash) REFERENCES commits(hash)
);

CREATE INDEX IF NOT EXISTS idx_file_changes_path ON file_changes(path);
CREATE INDEX IF NOT EXISTS idx_file_changes_commit ON file_changes(commit_hash);
CREATE INDEX IF NOT EXISTS idx_field_values_path ON field_values(path);
CREATE INDEX IF NOT EXISTS idx_field_values_json_path ON field_values(path, json_path);
CREATE INDEX IF NOT EXISTS idx_commits_timestamp ON commits(timestamp);
"""


def _flatten_json(obj: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """Flatten a JSON object into (json_path, value) pairs."""
    results: list[tuple[str, Any]] = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            results.extend(_flatten_json(val, path))
    elif isinstance(obj, list):
        for i, val in enumerate(obj):
            path = f"{prefix}[{i}]"
            results.extend(_flatten_json(val, path))
    else:
        results.append((prefix, obj))
    return results


class Index:
    """SQLite sidecar index for GitLedger."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def has_commit(self, hash_: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM commits WHERE hash = ?", (hash_,)
        ).fetchone()
        return row is not None

    def index_commit(
        self,
        commit: Commit,
        file_changes: list[FileChange],
        file_contents: dict[str, str | None],
    ) -> None:
        if self.has_commit(commit.hash):
            return

        self._conn.execute(
            "INSERT INTO commits (hash, timestamp, author, message, metadata_json, is_checkpoint) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                commit.hash,
                commit.timestamp.isoformat(),
                commit.author,
                commit.message,
                json.dumps(commit.metadata) if commit.metadata else None,
                1 if commit.is_checkpoint else 0,
            ),
        )

        for change in file_changes:
            self._conn.execute(
                "INSERT INTO file_changes (commit_hash, path, change_type, old_hash, new_hash) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    change.commit_hash,
                    change.path,
                    change.change_type.value,
                    change.old_hash,
                    change.new_hash,
                ),
            )

        for path, content in file_contents.items():
            if content is None:
                continue
            try:
                data = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                continue

            for json_path, value in _flatten_json(data):
                value_text = str(value) if value is not None else None
                value_numeric = None
                if isinstance(value, (int, float)):
                    value_numeric = float(value)
                self._conn.execute(
                    "INSERT INTO field_values (commit_hash, path, json_path, value_text, value_numeric) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (commit.hash, path, json_path, value_text, value_numeric),
                )

        self._conn.commit()

    def query_timeline(
        self,
        path: str,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[Commit]:
        query = (
            "SELECT DISTINCT c.hash, c.timestamp, c.author, c.message, c.metadata_json, c.is_checkpoint "
            "FROM commits c "
            "JOIN file_changes fc ON c.hash = fc.commit_hash "
            "WHERE fc.path = ?"
        )
        params: list[Any] = [path]

        if since:
            query += " AND c.timestamp >= ?"
            params.append(since.isoformat())
        if until:
            query += " AND c.timestamp <= ?"
            params.append(until.isoformat())

        query += " ORDER BY c.timestamp ASC"

        rows = self._conn.execute(query, params).fetchall()
        return [_row_to_commit(row) for row in rows]

    def query_trend(
        self,
        path: str,
        field: str,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[tuple[str, datetime, float]]:
        query = (
            "SELECT fv.commit_hash, c.timestamp, fv.value_numeric "
            "FROM field_values fv "
            "JOIN commits c ON fv.commit_hash = c.hash "
            "WHERE fv.path = ? AND fv.json_path = ? AND fv.value_numeric IS NOT NULL"
        )
        params: list[Any] = [path, field]

        if since:
            query += " AND c.timestamp >= ?"
            params.append(since.isoformat())
        if until:
            query += " AND c.timestamp <= ?"
            params.append(until.isoformat())

        query += " ORDER BY c.timestamp ASC"

        rows = self._conn.execute(query, params).fetchall()
        return [
            (row["commit_hash"], datetime.fromisoformat(row["timestamp"]), row["value_numeric"])
            for row in rows
        ]

    def query_field_values(
        self,
        path: str,
        json_path: str,
    ) -> list[FieldValue]:
        rows = self._conn.execute(
            "SELECT fv.commit_hash, fv.path, fv.json_path, fv.value_text "
            "FROM field_values fv "
            "JOIN commits c ON fv.commit_hash = c.hash "
            "WHERE fv.path = ? AND fv.json_path = ? "
            "ORDER BY c.timestamp ASC",
            (path, json_path),
        ).fetchall()
        return [
            FieldValue(
                commit_hash=row["commit_hash"],
                path=row["path"],
                json_path=row["json_path"],
                value=row["value_text"],
            )
            for row in rows
        ]

    def query_commits_by_hashes(
        self,
        hashes: set[str],
    ) -> list[Commit]:
        if not hashes:
            return []
        placeholders = ",".join("?" for _ in hashes)
        rows = self._conn.execute(
            f"SELECT hash, timestamp, author, message, metadata_json, is_checkpoint "
            f"FROM commits WHERE hash IN ({placeholders}) ORDER BY timestamp ASC",
            list(hashes),
        ).fetchall()
        return [_row_to_commit(row) for row in rows]

    def query_changes_by_path_pattern(
        self,
        pattern: str,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[FileChange]:
        sql_pattern = pattern.replace("*", "%")
        query = (
            "SELECT fc.commit_hash, fc.path, fc.change_type "
            "FROM file_changes fc "
            "JOIN commits c ON fc.commit_hash = c.hash "
            "WHERE fc.path LIKE ?"
        )
        params: list[Any] = [sql_pattern]

        if since:
            query += " AND c.timestamp >= ?"
            params.append(since.isoformat())
        if until:
            query += " AND c.timestamp <= ?"
            params.append(until.isoformat())

        query += " ORDER BY c.timestamp ASC"
        rows = self._conn.execute(query, params).fetchall()
        return [
            FileChange(
                commit_hash=row["commit_hash"],
                path=row["path"],
                change_type=ChangeType(row["change_type"]),
            )
            for row in rows
        ]

    def most_changed_paths(
        self,
        pattern: str | None = None,
        limit: int = 10,
    ) -> list[tuple[str, int]]:
        if pattern:
            sql_pattern = pattern.replace("*", "%")
            rows = self._conn.execute(
                "SELECT path, COUNT(*) as cnt FROM file_changes "
                "WHERE path LIKE ? GROUP BY path ORDER BY cnt DESC LIMIT ?",
                (sql_pattern, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT path, COUNT(*) as cnt FROM file_changes "
                "GROUP BY path ORDER BY cnt DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [(row["path"], row["cnt"]) for row in rows]

    def rebuild(self) -> None:
        self._conn.executescript(
            "DELETE FROM field_values; DELETE FROM file_changes; DELETE FROM commits;"
        )
        self._conn.commit()


def _row_to_commit(row: sqlite3.Row) -> Commit:
    metadata: dict = {}
    if row["metadata_json"]:
        try:
            metadata = json.loads(row["metadata_json"])
        except (json.JSONDecodeError, ValueError):
            pass
    return Commit(
        hash=row["hash"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        author=row["author"],
        message=row["message"],
        metadata=metadata,
        is_checkpoint=bool(row["is_checkpoint"]),
    )
