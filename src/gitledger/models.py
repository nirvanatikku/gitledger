"""Data models for GitLedger."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class ChangeType(enum.Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass(frozen=True, slots=True)
class Commit:
    hash: str
    timestamp: datetime
    message: str
    author: str
    metadata: dict[str, Any] = field(default_factory=dict)
    is_checkpoint: bool = False


@dataclass(frozen=True, slots=True)
class FileChange:
    commit_hash: str
    path: str
    change_type: ChangeType
    old_hash: str | None = None
    new_hash: str | None = None


@dataclass(frozen=True, slots=True)
class FieldValue:
    commit_hash: str
    path: str
    json_path: str
    value: Any = None


@dataclass(frozen=True, slots=True)
class DiffEntry:
    path: str
    field: str
    old_value: Any = None
    new_value: Any = None


@dataclass(frozen=True, slots=True)
class TrendPoint:
    commit_hash: str
    timestamp: datetime
    value: float


@dataclass(frozen=True, slots=True)
class Episode:
    id: str
    start_commit: str
    end_commit: str
    path_pattern: str
    episode_type: str
    commits: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Anomaly:
    commit_hash: str
    timestamp: datetime
    path: str
    field: str
    value: float
    expected_range: tuple[float, float]
    severity: float
