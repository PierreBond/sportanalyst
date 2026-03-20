from __future__ import annotations

import pytest

from services.biometric_service.src.injury_risk import (
    InjuryRiskModel,
    calculate_injury_risk,
    INJURY_PROBABILITY_THRESHOLD_HIGH,
    INJURY_PROBABILITY_THRESHOLD_MEDIUM,
)


class TestInjuryRiskModel:
    """Tests for the InjuryRiskModel class."""

    def test_high_acwr_produces_high_risk(self) -> None:
        model = InjuryRiskModel()
        result = model.predict_risk(acwr=1.8)
        assert result["injury_probability"] > 0.5
        assert any("ACWR" in f for f in result["risk_factors"])

    def test_optimal_acwr_produces_low_risk(self) -> None:
        model = InjuryRiskModel()
        result = model.predict_risk(acwr=1.0)
        assert result["injury_probability"] < INJURY_PROBABILITY_THRESHOLD_MEDIUM

    def test_poor_sleep_contributes_to_risk(self) -> None:
        model = InjuryRiskModel()
        result = model.predict_risk(sleep_score=30)
        assert result["injury_probability"] > 0
        assert any("sleep" in f.lower() for f in result["risk_factors"])

    def test_good_sleep_low_risk(self) -> None:
        model = InjuryRiskModel()
        result = model.predict_risk(sleep_score=90)
        assert result["risk_level"] == "low"

    def test_no_inputs_returns_zero_risk(self) -> None:
        model = InjuryRiskModel()
        result = model.predict_risk()
        assert result["injury_probability"] == 0.0
        assert result["risk_level"] == "low"
        assert result["risk_factors"] == []

    def test_risk_probability_bounded(self) -> None:
        model = InjuryRiskModel()
        result = model.predict_risk(
            acwr=2.5, hrv_7day_avg=10, resting_hr_trend=15,
            sleep_score=10, cumulative_load=20000,
        )
        assert 0.0 <= result["injury_probability"] <= 1.0

    def test_risk_levels(self) -> None:
        model = InjuryRiskModel()
        high = model.predict_risk(
            acwr=2.0, hrv_7day_avg=10, sleep_score=20,
            cumulative_load=18000, baseline_hrv=60,
        )
        assert high["risk_level"] == "high"

    def test_computed_at_present(self) -> None:
        model = InjuryRiskModel()
        result = model.predict_risk(acwr=1.0)
        assert "computed_at" in result

    def test_convenience_function(self) -> None:
        result = calculate_injury_risk(acwr=1.5, sleep_score=40)
        assert "injury_probability" in result
        assert "risk_level" in result
