"""Semantic diff engine for structured artifacts."""

from __future__ import annotations

import json
from typing import Any

from gitledger.models import DiffEntry


def semantic_diff(
    old_content: str | None,
    new_content: str | None,
    path: str,
) -> list[DiffEntry]:
    """Compute field-level diffs between two JSON documents."""
    if old_content is None and new_content is None:
        return []

    old_data = _parse_json(old_content)
    new_data = _parse_json(new_content)

    if old_data is None and new_data is None:
        if old_content != new_content:
            return [DiffEntry(path=path, field="<raw>", old_value=old_content, new_value=new_content)]
        return []

    if old_data is None:
        return [DiffEntry(path=path, field="<root>", old_value=None, new_value=new_data)]

    if new_data is None:
        return [DiffEntry(path=path, field="<root>", old_value=old_data, new_value=None)]

    entries: list[DiffEntry] = []
    _compare(old_data, new_data, path, "", entries)
    return entries


def _parse_json(content: str | None) -> Any:
    if content is None:
        return None
    try:
        return json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return None


def _compare(
    old: Any,
    new: Any,
    path: str,
    prefix: str,
    entries: list[DiffEntry],
) -> None:
    if type(old) is not type(new):
        entries.append(DiffEntry(
            path=path,
            field=prefix or "<root>",
            old_value=old,
            new_value=new,
        ))
        return

    if isinstance(old, dict):
        all_keys = set(old.keys()) | set(new.keys())
        for key in sorted(all_keys):
            field = f"{prefix}.{key}" if prefix else key
            if key not in old:
                entries.append(DiffEntry(path=path, field=field, old_value=None, new_value=new[key]))
            elif key not in new:
                entries.append(DiffEntry(path=path, field=field, old_value=old[key], new_value=None))
            else:
                _compare(old[key], new[key], path, field, entries)

    elif isinstance(old, list):
        max_len = max(len(old), len(new))
        for i in range(max_len):
            field = f"{prefix}[{i}]"
            if i >= len(old):
                entries.append(DiffEntry(path=path, field=field, old_value=None, new_value=new[i]))
            elif i >= len(new):
                entries.append(DiffEntry(path=path, field=field, old_value=old[i], new_value=None))
            else:
                _compare(old[i], new[i], path, field, entries)

    elif old != new:
        entries.append(DiffEntry(
            path=path,
            field=prefix or "<root>",
            old_value=old,
            new_value=new,
        ))
