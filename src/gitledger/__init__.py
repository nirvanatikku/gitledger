"""GitLedger: structural memory for agents and automation.

A Python library that turns a Git repository into a deterministic
temporal memory substrate.
"""

from gitledger.repo import Repo
from gitledger.models import (
    Commit,
    FileChange,
    FieldValue,
    DiffEntry,
    TrendPoint,
    Episode,
    Anomaly,
    ChangeType,
)

__version__ = "1.0.0"

__all__ = [
    "Repo",
    "Commit",
    "FileChange",
    "FieldValue",
    "DiffEntry",
    "TrendPoint",
    "Episode",
    "Anomaly",
    "ChangeType",
]
