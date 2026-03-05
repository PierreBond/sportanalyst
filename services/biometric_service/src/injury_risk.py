from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np

from sports_common.logging import get_logger

logger = get_logger(__name__)

INJURY_PROBABILITY_THRESHOLD_HIGH = 0.7
INJURY_PROBABILITY_THRESHOLD_MEDIUM = 0.4


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
        risk_factors = []
        risk_score = 0.0
        total_weight = 0.0

        if acwr is not None:
            acwr_contribution = self._calculate_acwr_risk(acwr)
            risk_score += acwr_contribution * self.weights["acwr"]
            total_weight += self.weights["acwr"]
            if acwr_contribution > 0.3:
                risk_factors.append(f"High ACWR ({acwr:.2f})")

        if hrv_7day_avg is not None:
            hrv_contribution = self._calculate_hrv_risk(hrv_7day_avg, baseline_hrv)
            risk_score += hrv_contribution * self.weights["hrv"]
            total_weight += self.weights["hrv"]
            if hrv_contribution > 0.3:
                risk_factors.append(f"Low HRV ({hrv_7day_avg:.0f}ms vs baseline {baseline_hrv:.0f})")

        if resting_hr_trend is not None:
            resting_hr_contribution = self._calculate_resting_hr_risk(resting_hr_trend)
            risk_score += resting_hr_contribution * self.weights["resting_hr"]
            total_weight += self.weights["resting_hr"]
            if resting_hr_contribution > 0.3:
                risk_factors.append(f"Elevated resting HR trend (+{resting_hr_trend:.1f} bpm)")

        if sleep_score is not None:
            sleep_contribution = self._calculate_sleep_risk(sleep_score)
            risk_score += sleep_contribution * self.weights["sleep"]
            total_weight += self.weights["sleep"]
            if sleep_contribution > 0.3:
                risk_factors.append(f"Poor sleep ({sleep_score:.0f}%)")

        if cumulative_load is not None:
            workload_contribution = self._calculate_workload_risk(cumulative_load)
            risk_score += workload_contribution * self.weights["workload"]
            total_weight += self.weights["workload"]
            if workload_contribution > 0.3:
                risk_factors.append(f"High cumulative load ({cumulative_load:.0f})")

        if total_weight > 0:
            normalized_risk = risk_score / total_weight
        else:
            normalized_risk = 0.0

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

    def _calculate_acwr_risk(self, acwr: float) -> float:
        """Calculate risk contribution from ACWR.

        Optimal range: 0.8 - 1.3
        Danger zone: >= 1.5
        """
        if acwr >= 1.5:
            return 1.0
        elif acwr >= 1.3:
            return 0.6 + (acwr - 1.3) * 2
        elif acwr >= 0.8:
            return 0.1
        else:
            return 0.3 + (0.8 - acwr)

    def _calculate_hrv_risk(self, hrv: float, baseline: float) -> float:
        """Calculate risk contribution from HRV.

        Lower HRV relative to baseline indicates elevated stress.
        """
        if hrv >= baseline:
            return 0.0

        percent_decline = (baseline - hrv) / baseline

        if percent_decline >= 0.3:
            return 1.0
        elif percent_decline >= 0.2:
            return 0.6
        elif percent_decline >= 0.1:
            return 0.3
        else:
            return 0.1

    def _calculate_resting_hr_risk(self, trend: float) -> float:
        """Calculate risk contribution from resting HR trend.

        Positive trend = increasing resting HR (bad)
        """
        if trend >= 10:
            return 1.0
        elif trend >= 5:
            return 0.7
        elif trend >= 2:
            return 0.4
        elif trend >= 0:
            return 0.2
        else:
            return 0.0

    def _calculate_sleep_risk(self, sleep_score: float) -> float:
        """Calculate risk contribution from sleep quality."""
        if sleep_score >= 85:
            return 0.0
        elif sleep_score >= 70:
            return 0.2
        elif sleep_score >= 50:
            return 0.5
        else:
            return 1.0

    def _calculate_workload_risk(self, cumulative_load: float) -> float:
        """Calculate risk contribution from cumulative season workload."""
        if cumulative_load >= 15000:
            return 1.0
        elif cumulative_load >= 10000:
            return 0.6
        elif cumulative_load >= 5000:
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
