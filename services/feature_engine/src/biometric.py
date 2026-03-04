from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

ACUTE_WINDOW_DAYS = 7
CHRONIC_WINDOW_DAYS = 28
DANGER_ZONE_THRESHOLD = 1.5


def compute_acwr(
    workload_series: pd.DataFrame,
    as_of: datetime,
) -> float:
    """Compute the Acute:Chronic Workload Ratio.

    Args:
        workload_series: DataFrame with columns ['recorded_at', 'value'].
            'value' represents daily PlayerLoad or equivalent.
        as_of: The timestamp to compute the ratio for.

    Returns:
        ACWR ratio. Values > 1.5 indicate the 'danger zone'.
    """
    as_of_utc = as_of.astimezone(timezone.utc)
    acute_start = as_of_utc - timedelta(days=ACUTE_WINDOW_DAYS)
    chronic_start = as_of_utc - timedelta(days=CHRONIC_WINDOW_DAYS)

    acute_data = workload_series[
        (workload_series["recorded_at"] >= acute_start)
        & (workload_series["recorded_at"] <= as_of_utc)
    ]
    chronic_data = workload_series[
        (workload_series["recorded_at"] >= chronic_start)
        & (workload_series["recorded_at"] <= as_of_utc)
    ]

    if acute_data.empty or chronic_data.empty:
        return 0.0

    acute_load = acute_data["value"].sum()
    chronic_avg = chronic_data["value"].sum() / (CHRONIC_WINDOW_DAYS / ACUTE_WINDOW_DAYS)

    if chronic_avg == 0:
        return 0.0

    return round(acute_load / chronic_avg, 4)


def is_danger_zone(acwr: float) -> bool:
    """Check if ACWR indicates injury risk."""
    return acwr >= DANGER_ZONE_THRESHOLD


def compute_team_avg_acwr(
    player_workloads: dict[str, pd.DataFrame],
) -> float:
    """Compute average ACWR across all players in a team."""
    acwrs = []
    now = datetime.now(timezone.utc)

    for player_id, workload in player_workloads.items():
        if not workload.empty:
            acwr = compute_acwr(workload, now)
            if acwr > 0:
                acwrs.append(acwr)

    if not acwrs:
        return 0.0

    return sum(acwrs) / len(acwrs)


def compute_team_avg_hrv(
    biometric_data: pd.DataFrame,
) -> float:
    """Compute average HRV across a team's players."""
    hrv_data = biometric_data[biometric_data["metric_type"] == "hrv"]

    if hrv_data.empty:
        return 0.0

    return hrv_data["value"].mean()


def aggregate_team_biometrics(
    player_biometrics: dict[str, pd.DataFrame],
) -> dict[str, float]:
    """Aggregate biometric features for a team.

    Args:
        player_biometrics: Dict mapping player_id to their biometric DataFrame

    Returns:
        Dict of aggregated features
    """
    features = {
        "team_avg_acwr": compute_team_avg_acwr(player_biometrics),
        "team_avg_hrv": 0.0,
        "team_avg_player_load": 0.0,
    }

    all_data = pd.concat(player_biometrics.values(), ignore_index=True)

    if not all_data.empty:
        hrv_data = all_data[all_data["metric_type"] == "hrv"]
        if not hrv_data.empty:
            features["team_avg_hrv"] = hrv_data["value"].mean()

        load_data = all_data[all_data["metric_type"] == "player_load"]
        if not load_data.empty:
            features["team_avg_player_load"] = load_data["value"].mean()

    return features


def compute_injury_risk_factors(
    acwr: float,
    hrv_trend: float,
    rest_days: int,
) -> list[str]:
    """Compute injury risk factors based on biometric indicators."""
    factors = []

    if acwr >= DANGER_ZONE_THRESHOLD:
        factors.append("high_acwr")

    if hrv_trend < -10:
        factors.append("declining_hrv")

    if rest_days < 3:
        factors.append("short_rest")

    return factors
