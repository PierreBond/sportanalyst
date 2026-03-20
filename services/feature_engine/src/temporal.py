from __future__ import annotations

from typing import Any

import pandas as pd


def add_rolling_avg(
    df: pd.DataFrame,
    column: str,
    window_size: int,
    group_by: list[str],
    output_name: str,
) -> pd.DataFrame:
    """Add a rolling average feature to the DataFrame.

    Args:
        df: Input DataFrame, sorted by match date.
        column: Source column to average.
        window_size: Number of preceding rows to include.
        group_by: Partition columns (e.g., ['team_id']).
        output_name: Name of the new feature column.

    Returns:
        DataFrame with the new column appended.
    """
    result = df.copy()
    result = result.sort_values(by=group_by + ["match_datetime"])
    result[output_name] = (
        result.groupby(group_by)[column]
        .transform(lambda x: x.rolling(window=window_size, min_periods=1).mean())
    )
    return result


def add_rolling_std(
    df: pd.DataFrame,
    column: str,
    window_size: int,
    group_by: list[str],
    output_name: str,
) -> pd.DataFrame:
    """Add a rolling standard deviation feature."""
    result = df.copy()
    result = result.sort_values(by=group_by + ["match_datetime"])
    result[output_name] = (
        result.groupby(group_by)[column]
        .transform(lambda x: x.rolling(window=window_size, min_periods=1).std())
    )
    return result


def add_momentum_slope(
    df: pd.DataFrame,
    column: str,
    window_size: int,
    group_by: list[str],
    output_name: str,
) -> pd.DataFrame:
    """Add a linear regression slope feature (momentum indicator)."""
    result = df.copy()
    result = result.sort_values(by=group_by + ["match_datetime"])

    def linear_slope(series: pd.Series) -> float:
        if len(series) < 2:
            return 0.0
        x = pd.Series(range(len(series)))
        if series.std() == 0:
            return 0.0
        correlation = series.corr(x)
        slope = correlation * (series.std() / x.std() if x.std() > 0 else 0)
        return slope

    result[output_name] = (
        result.groupby(group_by)[column]
        .transform(lambda x: x.rolling(window=window_size, min_periods=2).apply(linear_slope, raw=False))
    )
    return result


def add_lag_feature(
    df: pd.DataFrame,
    column: str,
    lag: int,
    group_by: list[str],
    output_name: str | None = None,
) -> pd.DataFrame:
    """Add a lag feature."""
    result = df.copy()
    result = result.sort_values(by=group_by + ["match_datetime"])
    output = output_name or f"lag_{lag}_{column}"
    result[output] = result.groupby(group_by)[column].shift(lag)
    return result


def add_idw_weighted(
    df: pd.DataFrame,
    column: str,
    decay_factor: float,
    group_by: list[str],
    output_name: str,
) -> pd.DataFrame:
    """Add Inverse Distance Weighted feature with exponential decay."""
    result = df.copy()
    result = result.sort_values(by=group_by + ["match_datetime"])

    def weighted_avg(series: pd.Series) -> float:
        if len(series) == 0:
            return 0.0
        weights = [decay_factor**i for i in range(len(series) - 1, -1, -1)]
        return sum(w * v for w, v in zip(weights, series)) / sum(weights)

    result[output_name] = (
        result.groupby(group_by)[column]
        .transform(lambda x: x.expanding().apply(weighted_avg, raw=False))
    )
    return result


def add_rest_days(df: pd.DataFrame, output_name: str = "rest_days") -> pd.DataFrame:
    """Calculate days since team's last match."""
    result = df.copy()
    result = result.sort_values(by=["team_id", "match_datetime"])
    result[output_name] = (
        result.groupby("team_id")["match_datetime"]
        .diff()
        .dt.days
    )
    result[output_name] = result[output_name].fillna(7)
    return result


def compute_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all temporal features for a match DataFrame."""
    result = df.copy()

    if "goals_scored" in result.columns:
        result = add_rolling_avg(result, "goals_scored", 5, ["team_id", "venue_type"], "rolling_avg_goals_5")
        result = add_rolling_avg(result, "goals_scored", 10, ["team_id"], "rolling_avg_goals_10")
        result = add_rolling_std(result, "goals_scored", 5, ["team_id"], "rolling_std_goals_5")
        result = add_lag_feature(result, "goals_scored", 1, ["team_id"], "lag_1_goals")
        result = add_lag_feature(result, "goals_scored", 2, ["team_id"], "lag_2_goals")
        result = add_lag_feature(result, "goals_scored", 3, ["team_id"], "lag_3_goals")

    if "xg" in result.columns:
        result = add_rolling_avg(result, "xg", 5, ["team_id"], "rolling_avg_xg_5")
        result = add_momentum_slope(result, "xg", 5, ["team_id"], "momentum_xg_slope_5")
        result = add_momentum_slope(result, "xg", 12, ["team_id"], "momentum_xg_slope_12")

    result = add_rest_days(result)

    return result
