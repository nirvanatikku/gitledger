"""Narrative summary generation from repository history."""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from gitledger.models import Commit, FileChange


def narrate(
    commits: list[Commit],
    changes: list[FileChange],
    since: datetime | None = None,
    until: datetime | None = None,
) -> str:
    """Generate a human-readable narrative from commits and changes."""
    if not commits:
        return "No activity in the specified time window."

    filtered = commits
    if since:
        filtered = [c for c in filtered if c.timestamp >= since]
    if until:
        filtered = [c for c in filtered if c.timestamp <= until]

    if not filtered:
        return "No activity in the specified time window."

    lines: list[str] = []

    first = filtered[0]
    last = filtered[-1]
    lines.append(
        f"Between {first.timestamp.strftime('%Y-%m-%d %H:%M')} and "
        f"{last.timestamp.strftime('%Y-%m-%d %H:%M')}, "
        f"{len(filtered)} commit{'s' if len(filtered) != 1 else ''} "
        f"{'were' if len(filtered) != 1 else 'was'} recorded."
    )

    path_counts: Counter[str] = Counter()
    for change in changes:
        if any(c.hash == change.commit_hash for c in filtered):
            path_counts[change.path] += 1

    if path_counts:
        top = path_counts.most_common(5)
        lines.append("")
        lines.append("Most active files:")
        for path, count in top:
            lines.append(f"  - {path} ({count} change{'s' if count != 1 else ''})")

    authors: Counter[str] = Counter(c.author for c in filtered)
    if len(authors) > 1:
        lines.append("")
        lines.append("Contributors:")
        for author, count in authors.most_common():
            lines.append(f"  - {author} ({count} commit{'s' if count != 1 else ''})")

    checkpoints = [c for c in filtered if c.is_checkpoint]
    if checkpoints:
        lines.append("")
        lines.append(f"{len(checkpoints)} checkpoint{'s' if len(checkpoints) != 1 else ''} recorded.")

    event_types: Counter[str] = Counter()
    for c in filtered:
        if c.message.startswith("event:"):
            parts = c.message.split(":")
            if len(parts) >= 3:
                event_types[parts[2]] += 1

    if event_types:
        lines.append("")
        lines.append("Event types:")
        for event_type, count in event_types.most_common():
            lines.append(f"  - {event_type} ({count})")

    return "\n".join(lines)
