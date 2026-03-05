from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sports_common.logging import get_logger

logger = get_logger(__name__)

WELLNESS_THRESHOLD_HIGH = 70
WELLNESS_THRESHOLD_MEDIUM = 40


class WellnessCalculator:
    """Calculate team and player wellness scores from biometric data.

    Aggregates:
    - HRV (higher is better)
    - Resting heart rate (lower is better)
    - Sleep quality score (higher is better)
    - Recovery score (higher is better)
    """

    def __init__(
        self,
        hrv_weight: float = 0.30,
        resting_hr_weight: float = 0.20,
        sleep_weight: float = 0.30,
        recovery_weight: float = 0.20,
    ) -> None:
        self.weights = {
            "hrv": hrv_weight,
            "resting_hr": resting_hr_weight,
            "sleep": sleep_weight,
            "recovery": recovery_weight,
        }

    def calculate_player_wellness(
        self,
        hrv: float | None = None,
        resting_hr: float | None = None,
        sleep_score: float | None = None,
        recovery_score: float | None = None,
        baseline_hrv: float = 50.0,
        baseline_resting_hr: float = 55.0,
    ) -> dict[str, Any]:
        """Calculate wellness for a single player.

        Args:
            hrv: Heart rate variability (ms)
            resting_hr: Resting heart rate (bpm)
            sleep_score: Sleep quality (0-100)
            recovery_score: Recovery score (0-100)
            baseline_hrv: Player's baseline HRV
            baseline_resting_hr: Player's baseline resting HR

        Returns:
            Dict with wellness_score, status, and component scores
        """
        scores = {}
        total_weight = 0.0

        if hrv is not None:
            hrv_score = self._normalize_hrv(hrv, baseline_hrv)
            scores["hrv"] = hrv_score
            total_weight += self.weights["hrv"]

        if resting_hr is not None:
            resting_hr_score = self._normalize_resting_hr(resting_hr, baseline_resting_hr)
            scores["resting_hr"] = resting_hr_score
            total_weight += self.weights["resting_hr"]

        if sleep_score is not None:
            scores["sleep"] = sleep_score / 100.0
            total_weight += self.weights["sleep"]

        if recovery_score is not None:
            scores["recovery"] = recovery_score / 100.0
            total_weight += self.weights["recovery"]

        if total_weight > 0:
            wellness_score = sum(
                score * self.weights.get(component, 0)
                for component, score in scores.items()
            ) / sum(
                self.weights.get(component, 0)
                for component in scores.keys()
            )
        else:
            wellness_score = 0.5

        wellness_score = round(min(max(wellness_score, 0.0), 1.0), 3)

        if wellness_score >= WELLNESS_THRESHOLD_HIGH / 100:
            status = "ready"
        elif wellness_score >= WELLNESS_THRESHOLD_MEDIUM / 100:
            status = "moderate"
        else:
            status = "fatigued"

        return {
            "wellness_score": wellness_score,
            "status": status,
            "components": scores,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    def calculate_team_wellness(
        self,
        player_wellness: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Calculate aggregated team wellness.

        Args:
            player_wellness: List of player wellness dicts from calculate_player_wellness

        Returns:
            Dict with team_avg_wellness, player_count, readiness_status
        """
        if not player_wellness:
            return {
                "team_avg_wellness": 0.0,
                "player_count": 0,
                "status": "no_data",
                "readiness_pct": 0.0,
            }

        wellness_scores = [p["wellness_score"] for p in player_wellness]
        avg_wellness = sum(wellness_scores) / len(wellness_scores)

        ready_count = sum(1 for p in player_wellness if p["status"] == "ready")
        moderate_count = sum(1 for p in player_wellness if p["status"] == "moderate")
        fatigued_count = sum(1 for p in player_wellness if p["status"] == "fatigued")

        readiness_pct = (ready_count / len(player_wellness)) * 100

        if readiness_pct >= 80:
            readiness_status = "optimal"
        elif readiness_pct >= 60:
            readiness_status = "good"
        elif readiness_pct >= 40:
            readiness_status = "concerning"
        else:
            readiness_status = "critical"

        return {
            "team_avg_wellness": round(avg_wellness, 3),
            "player_count": len(player_wellness),
            "ready_count": ready_count,
            "moderate_count": moderate_count,
            "fatigued_count": fatigued_count,
            "readiness_pct": round(readiness_pct, 1),
            "readiness_status": readiness_status,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    def _normalize_hrv(self, hrv: float, baseline: float) -> float:
        """Normalize HRV to 0-1 scale (higher is better)."""
        if baseline <= 0:
            return 0.5

        ratio = hrv / baseline
        if ratio >= 1.0:
            return 1.0
        elif ratio >= 0.8:
            return 0.5 + (ratio - 0.8) / 0.2 * 0.5
        else:
            return ratio / 0.8 * 0.5

    def _normalize_resting_hr(self, resting_hr: float, baseline: float) -> float:
        """Normalize resting HR to 0-1 scale (lower is better)."""
        if baseline <= 0:
            return 0.5

        ratio = resting_hr / baseline
        if ratio <= 1.0:
            return 1.0
        elif ratio <= 1.15:
            return 1.0 - (ratio - 1.0) / 0.15 * 0.5
        else:
            return max(0, 1.0 - (ratio - 1.0))


def calculate_player_wellness(
    hrv: float | None = None,
    resting_hr: float | None = None,
    sleep_score: float | None = None,
    recovery_score: float | None = None,
) -> dict[str, Any]:
    """Convenience function for player wellness calculation."""
    calculator = WellnessCalculator()
    return calculator.calculate_player_wellness(
        hrv=hrv,
        resting_hr=resting_hr,
        sleep_score=sleep_score,
        recovery_score=recovery_score,
    )
