from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.biometric_service.src.acwr import (
    compute_acwr,
    get_acwr_status,
    is_danger_zone,
    is_optimal_zone,
)


class TestComputeACWR:
    """Tests for ACWR computation."""

    def test_empty_workload_returns_zeros(self) -> None:
        now = datetime.now(timezone.utc)
        acwr, acute, chronic = compute_acwr([], now)
        assert acwr == 0.0
        assert acute == 0.0
        assert chronic == 0.0

    def test_uniform_workload_returns_near_one(self) -> None:
        now = datetime.now(timezone.utc)
        workload = [{"recorded_at": now - timedelta(days=i), "value": 100} for i in range(28)]
        acwr, acute, chronic = compute_acwr(workload, now)
        assert 0.8 <= acwr <= 1.3

    def test_spike_workload_returns_high_acwr(self) -> None:
        now = datetime.now(timezone.utc)
        workload = []
        for i in range(28, 7, -1):
            workload.append({"recorded_at": now - timedelta(days=i), "value": 50})
        for i in range(7, 0, -1):
            workload.append({"recorded_at": now - timedelta(days=i), "value": 200})
        acwr, acute, chronic = compute_acwr(workload, now)
        assert acwr > 1.3

    def test_as_of_respects_cutoff(self) -> None:
        now = datetime.now(timezone.utc)
        workload = [{"recorded_at": now - timedelta(days=i), "value": 100} for i in range(30)]
        workload.append({"recorded_at": now + timedelta(days=1), "value": 10000})
        acwr_before, _, _ = compute_acwr(workload, now)
        assert acwr_before < 2.0


class TestACWRHelpers:
    """Tests for ACWR helper functions."""

    def test_is_danger_zone_true(self) -> None:
        assert is_danger_zone(1.5) is True
        assert is_danger_zone(2.0) is True

    def test_is_danger_zone_false(self) -> None:
        assert is_danger_zone(1.0) is False
        assert is_danger_zone(1.4) is False

    def test_is_optimal_zone(self) -> None:
        assert is_optimal_zone(1.0) is True
        assert is_optimal_zone(0.8) is True
        assert is_optimal_zone(1.3) is True
        assert is_optimal_zone(0.5) is False
        assert is_optimal_zone(1.6) is False

    def test_get_acwr_status(self) -> None:
        assert get_acwr_status(1.0) == "optimal"
        assert get_acwr_status(1.5) == "danger"
