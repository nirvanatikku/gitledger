"""Tests for trend extraction and anomaly detection."""

from datetime import datetime, timezone

from gitledger.models import TrendPoint
from gitledger.trend import detect_anomalies, extract_trend


class TestExtractTrend:
    def test_basic(self):
        data = [
            ("abc", datetime(2026, 1, 1, tzinfo=timezone.utc), 1.0),
            ("def", datetime(2026, 1, 2, tzinfo=timezone.utc), 2.0),
            ("ghi", datetime(2026, 1, 3, tzinfo=timezone.utc), 3.0),
        ]
        points = extract_trend(data)
        assert len(points) == 3
        assert points[0].value == 1.0
        assert points[2].value == 3.0

    def test_empty(self):
        assert extract_trend([]) == []


class TestDetectAnomalies:
    def test_detects_outlier(self):
        points = [
            TrendPoint("a", datetime(2026, 1, i, tzinfo=timezone.utc), 10.0)
            for i in range(1, 11)
        ]
        points.append(
            TrendPoint("outlier", datetime(2026, 1, 11, tzinfo=timezone.utc), 100.0)
        )
        anomalies = detect_anomalies(points, "test.json", "score", sigma=2.0)
        assert len(anomalies) >= 1
        assert anomalies[0].commit_hash == "outlier"

    def test_no_anomalies_when_stable(self):
        points = [
            TrendPoint(f"c{i}", datetime(2026, 1, i, tzinfo=timezone.utc), 10.0)
            for i in range(1, 11)
        ]
        anomalies = detect_anomalies(points, "test.json", "score")
        assert anomalies == []

    def test_too_few_points(self):
        points = [
            TrendPoint("a", datetime(2026, 1, 1, tzinfo=timezone.utc), 1.0),
            TrendPoint("b", datetime(2026, 1, 2, tzinfo=timezone.utc), 100.0),
        ]
        anomalies = detect_anomalies(points, "test.json", "score")
        assert anomalies == []
