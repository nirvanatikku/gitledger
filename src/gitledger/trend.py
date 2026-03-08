"""Trend extraction and anomaly detection."""

from __future__ import annotations

import statistics
from datetime import datetime

from gitledger.models import Anomaly, TrendPoint


def extract_trend(
    data: list[tuple[str, datetime, float]],
) -> list[TrendPoint]:
    """Convert raw index data into TrendPoint objects."""
    return [
        TrendPoint(commit_hash=hash_, timestamp=ts, value=val)
        for hash_, ts, val in data
    ]


def detect_anomalies(
    points: list[TrendPoint],
    path: str,
    field: str,
    sigma: float = 2.0,
) -> list[Anomaly]:
    """Detect anomalies using z-score with configurable sigma threshold."""
    if len(points) < 3:
        return []

    values = [p.value for p in points]
    mean = statistics.mean(values)
    stdev = statistics.stdev(values)

    if stdev == 0:
        return []

    anomalies: list[Anomaly] = []
    low = mean - sigma * stdev
    high = mean + sigma * stdev

    for point in points:
        if point.value < low or point.value > high:
            z = abs(point.value - mean) / stdev
            anomalies.append(Anomaly(
                commit_hash=point.commit_hash,
                timestamp=point.timestamp,
                path=path,
                field=field,
                value=point.value,
                expected_range=(low, high),
                severity=z,
            ))

    return anomalies
