from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np

from sports_common.logging import get_logger

logger = get_logger(__name__)

INJURY_PROBABILITY_THRESHOLD_HIGH = 0.7
INJURY_PROBABILITY_THRESHOLD_MEDIUM = 0.4

# Risk factor reporting threshold
RISK_FACTOR_REPORT_THRESHOLD = 0.3

# ACWR thresholds
ACWR_DANGER_ZONE = 1.5
ACWR_ELEVATED = 1.3
ACWR_OPTIMAL_LOW = 0.8
ACWR_DANGER_RISK = 1.0
ACWR_ELEVATED_BASE_RISK = 0.6
ACWR_ELEVATED_SCALE = 2
ACWR_OPTIMAL_RISK = 0.1
ACWR_LOW_BASE_RISK = 0.3

# HRV thresholds (percent decline from baseline)
HRV_DECLINE_SEVERE = 0.3
HRV_DECLINE_MODERATE = 0.2
HRV_DECLINE_MILD = 0.1
HRV_RISK_SEVERE = 1.0
HRV_RISK_MODERATE = 0.6
HRV_RISK_MILD = 0.3
HRV_RISK_MINIMAL = 0.1

# Resting HR trend thresholds (bpm increase)
RESTING_HR_SEVERE = 10
RESTING_HR_ELEVATED = 5
RESTING_HR_MODERATE = 2

# Sleep score thresholds
SLEEP_EXCELLENT = 85
SLEEP_GOOD = 70
SLEEP_FAIR = 50

# Cumulative workload thresholds
WORKLOAD_VERY_HIGH = 15000
WORKLOAD_HIGH = 10000
WORKLOAD_MODERATE = 5000


class InjuryRiskModel:
    """Injury risk classifier based on biometric indicators.

    Uses heuristic rules based on:
    - ACWR (7/28 day ratio)
    - Rolling HRV (7-day average)
    - Resting HR trend
    - Sleep quality score
    - Cumulative PlayerLoad (season)

    In production, this would be an XGBoost classifier trained on historical data.
    """

    def __init__(
        self,
        acwr_weight: float = 0.35,
        hrv_weight: float = 0.25,
        resting_hr_weight: float = 0.15,
        sleep_weight: float = 0.15,
        workload_weight: float = 0.10,
    ) -> None:
        self.weights = {
            "acwr": acwr_weight,
            "hrv": hrv_weight,
            "resting_hr": resting_hr_weight,
            "sleep": sleep_weight,
            "workload": workload_weight,
        }

    def predict_risk(
        self,
        acwr: float | None = None,
        hrv_7day_avg: float | None = None,
        resting_hr_trend: float | None = None,
        sleep_score: float | None = None,
        cumulative_load: float | None = None,
        baseline_hrv: float = 50.0,
    ) -> dict[str, Any]:
        """Predict injury risk probability.

        Args:
            acwr: Acute:Chronic Workload Ratio
            hrv_7day_avg: 7-day average HRV
            resting_hr_trend: Change in resting HR (positive = worsening)
            sleep_score: Sleep quality score (0-100)
            cumulative_load: Cumulative season player load
            baseline_hrv: Player's baseline HRV for comparison

        Returns:
            Dict with risk_probability, risk_level, and risk_factors
        """
        risk_score, total_weight, risk_factors = self._collect_risk_contributions(
            acwr=acwr,
            hrv_7day_avg=hrv_7day_avg,
            resting_hr_trend=resting_hr_trend,
            sleep_score=sleep_score,
            cumulative_load=cumulative_load,
            baseline_hrv=baseline_hrv,
        )

        normalized_risk = risk_score / total_weight if total_weight > 0 else 0.0
        normalized_risk = round(min(max(normalized_risk, 0.0), 1.0), 4)

        if normalized_risk >= INJURY_PROBABILITY_THRESHOLD_HIGH:
            risk_level = "high"
        elif normalized_risk >= INJURY_PROBABILITY_THRESHOLD_MEDIUM:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "injury_probability": normalized_risk,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    def _collect_risk_contributions(
        self,
        acwr: float | None,
        hrv_7day_avg: float | None,
        resting_hr_trend: float | None,
        sleep_score: float | None,
        cumulative_load: float | None,
        baseline_hrv: float,
    ) -> tuple[float, float, list[str]]:
        """Collect weighted risk contributions from each biometric indicator.

        Returns:
            Tuple of (risk_score, total_weight, risk_factors).
        """
        risk_factors: list[str] = []
        risk_score = 0.0
        total_weight = 0.0

        indicators = [
            (acwr, "acwr", lambda v: self._calculate_acwr_risk(v),
             lambda v, c: f"High ACWR ({v:.2f})" if c > RISK_FACTOR_REPORT_THRESHOLD else None),
            (hrv_7day_avg, "hrv", lambda v: self._calculate_hrv_risk(v, baseline_hrv),
             lambda v, c: f"Low HRV ({v:.0f}ms vs baseline {baseline_hrv:.0f})" if c > RISK_FACTOR_REPORT_THRESHOLD else None),
            (resting_hr_trend, "resting_hr", lambda v: self._calculate_resting_hr_risk(v),
             lambda v, c: f"Elevated resting HR trend (+{v:.1f} bpm)" if c > RISK_FACTOR_REPORT_THRESHOLD else None),
            (sleep_score, "sleep", lambda v: self._calculate_sleep_risk(v),
             lambda v, c: f"Poor sleep ({v:.0f}%)" if c > RISK_FACTOR_REPORT_THRESHOLD else None),
            (cumulative_load, "workload", lambda v: self._calculate_workload_risk(v),
             lambda v, c: f"High cumulative load ({v:.0f})" if c > RISK_FACTOR_REPORT_THRESHOLD else None),
        ]

        for value, weight_key, calc_fn, label_fn in indicators:
            if value is not None:
                contribution = calc_fn(value)
                risk_score += contribution * self.weights[weight_key]
                total_weight += self.weights[weight_key]
                label = label_fn(value, contribution)
                if label:
                    risk_factors.append(label)

        return risk_score, total_weight, risk_factors

    def _calculate_acwr_risk(self, acwr: float) -> float:
        """Calculate risk contribution from ACWR.

        Optimal range: 0.8 - 1.3
        Danger zone: >= 1.5
        """
        if acwr >= ACWR_DANGER_ZONE:
            return ACWR_DANGER_RISK
        elif acwr >= ACWR_ELEVATED:
            return ACWR_ELEVATED_BASE_RISK + (acwr - ACWR_ELEVATED) * ACWR_ELEVATED_SCALE
        elif acwr >= ACWR_OPTIMAL_LOW:
            return ACWR_OPTIMAL_RISK
        else:
            return ACWR_LOW_BASE_RISK + (ACWR_OPTIMAL_LOW - acwr)

    def _calculate_hrv_risk(self, hrv: float, baseline: float) -> float:
        """Calculate risk contribution from HRV.

        Lower HRV relative to baseline indicates elevated stress.
        """
        if hrv >= baseline:
            return 0.0

        percent_decline = (baseline - hrv) / baseline

        if percent_decline >= HRV_DECLINE_SEVERE:
            return HRV_RISK_SEVERE
        elif percent_decline >= HRV_DECLINE_MODERATE:
            return HRV_RISK_MODERATE
        elif percent_decline >= HRV_DECLINE_MILD:
            return HRV_RISK_MILD
        else:
            return HRV_RISK_MINIMAL

    def _calculate_resting_hr_risk(self, trend: float) -> float:
        """Calculate risk contribution from resting HR trend.

        Positive trend = increasing resting HR (bad)
        """
        if trend >= RESTING_HR_SEVERE:
            return 1.0
        elif trend >= RESTING_HR_ELEVATED:
            return 0.7
        elif trend >= RESTING_HR_MODERATE:
            return 0.4
        elif trend >= 0:
            return 0.2
        else:
            return 0.0

    def _calculate_sleep_risk(self, sleep_score: float) -> float:
        """Calculate risk contribution from sleep quality."""
        if sleep_score >= SLEEP_EXCELLENT:
            return 0.0
        elif sleep_score >= SLEEP_GOOD:
            return 0.2
        elif sleep_score >= SLEEP_FAIR:
            return 0.5
        else:
            return 1.0

    def _calculate_workload_risk(self, cumulative_load: float) -> float:
        """Calculate risk contribution from cumulative season workload."""
        if cumulative_load >= WORKLOAD_VERY_HIGH:
            return 1.0
        elif cumulative_load >= WORKLOAD_HIGH:
            return 0.6
        elif cumulative_load >= WORKLOAD_MODERATE:
            return 0.3
        else:
            return 0.1


def calculate_injury_risk(
    acwr: float | None = None,
    hrv: float | None = None,
    resting_hr: float | None = None,
    sleep_score: float | None = None,
    player_load: float | None = None,
) -> dict[str, Any]:
    """Convenience function for injury risk calculation."""
    model = InjuryRiskModel()
    return model.predict_risk(
        acwr=acwr,
        hrv_7day_avg=hrv,
        resting_hr_trend=resting_hr,
        sleep_score=sleep_score,
        cumulative_load=player_load,
    )
