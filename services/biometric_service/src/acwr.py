from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

import structlog

logger = structlog.get_logger(__name__)

ACUTE_WINDOW_DAYS = 7
CHRONIC_WINDOW_DAYS = 28
DANGER_ZONE_THRESHOLD = 1.5
OPTIMAL_ZONE_MIN = 0.8
OPTIMAL_ZONE_MAX = 1.3


def compute_acwr(
    workload_data: list[dict[str, Any]],
    as_of: datetime,
) -> tuple[float, float, float]:
    """Compute the Acute:Chronic Workload Ratio.

    Args:
        workload_data: List of dicts with 'recorded_at' and 'value' keys.
            'value' represents daily PlayerLoad or equivalent.
        as_of: The timestamp to compute the ratio for.

    Returns:
        Tuple of (acwr, acute_load, chronic_avg)
    """
    as_of_utc = as_of.astimezone(timezone.utc)
    acute_start = as_of_utc - timedelta(days=ACUTE_WINDOW_DAYS)
    chronic_start = as_of_utc - timedelta(days=CHRONIC_WINDOW_DAYS)

    df = pd.DataFrame(workload_data)
    if df.empty:
        return 0.0, 0.0, 0.0

    df["recorded_at"] = pd.to_datetime(df["recorded_at"])
    df = df.sort_values("recorded_at")

    acute_data = df[(df["recorded_at"] >= acute_start) & (df["recorded_at"] <= as_of_utc)]
    chronic_data = df[(df["recorded_at"] >= chronic_start) & (df["recorded_at"] <= as_of_utc)]

    acute_load = acute_data["value"].sum()
    chronic_periods = CHRONIC_WINDOW_DAYS / ACUTE_WINDOW_DAYS
    chronic_avg = chronic_data["value"].sum() / chronic_periods if chronic_periods > 0 else 0

    if chronic_avg == 0:
        return 0.0, acute_load, 0.0

    acwr = round(acute_load / chronic_avg, 4)
    return acwr, acute_load, chronic_avg


def is_danger_zone(acwr: float) -> bool:
    """Check if ACWR indicates injury risk (>= 1.5)."""
    return acwr >= DANGER_ZONE_THRESHOLD


def is_optimal_zone(acwr: float) -> bool:
    """Check if ACWR is in optimal range (0.8 - 1.3)."""
    return OPTIMAL_ZONE_MIN <= acwr <= OPTIMAL_ZONE_MAX


def get_acwr_status(acwr: float) -> str:
    """Get the ACWR status category.

    Returns:
        - 'danger': ACWR >= 1.5 (high injury risk)
        - 'high': ACWR 1.3 - 1.5 (elevated risk)
        - 'optimal': ACWR 0.8 - 1.3 (optimal zone)
        - 'low': ACWR < 0.8 (undertraining)
    """
    if acwr >= DANGER_ZONE_THRESHOLD:
        return "danger"
    elif acwr >= OPTIMAL_ZONE_MAX:
        return "high"
    elif acwr >= OPTIMAL_ZONE_MIN:
        return "optimal"
    else:
        return "low"


def compute_rolling_acwr(
    workload_data: list[dict[str, Any]],
    compute_dates: list[datetime],
) -> list[dict[str, Any]]:
    """Compute ACWR for multiple dates (for trend analysis).

    Args:
        workload_data: Historical workload data
        compute_dates: List of dates to compute ACWR for

    Returns:
        List of dicts with date, acwr, acute_load, chronic_load, status
    """
    df = pd.DataFrame(workload_data)
    if df.empty:
        return []

    df["recorded_at"] = pd.to_datetime(df["recorded_at"])

    results = []
    for date in sorted(compute_dates):
        acwr, acute_load, chronic_avg = compute_acwr(
            workload_data,
            date,
        )
        results.append(
            {
                "date": date,
                "acwr": acwr,
                "acute_load": round(acute_load, 2),
                "chronic_load": round(chronic_avg, 2),
                "status": get_acwr_status(acwr),
                "is_danger_zone": is_danger_zone(acwr),
            }
        )

    return results
