from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pandas as pd


def odds_to_implied_probability(odds: float | Decimal) -> float:
    """Convert decimal odds to implied probability."""
    if float(odds) <= 0:
        return 0.0
    return 1.0 / float(odds)


def american_odds_to_decimal(odds: int | float) -> float:
    """Convert American odds to decimal odds."""
    odds = float(odds)
    if odds > 0:
        return (odds / 100) + 1
    else:
        return (100 / abs(odds)) + 1


def calculate_implied_probabilities(
    home_odds: float | Decimal,
    away_odds: float | Decimal,
    draw_odds: float | Decimal | None = None,
) -> tuple[float, float, float | None]:
    """Calculate implied probabilities from odds, removing vigorish."""
    home_implied = odds_to_implied_probability(home_odds)
    away_implied = odds_to_implied_probability(away_odds)

    if draw_odds is not None:
        draw_implied = odds_to_implied_probability(draw_odds)
        total = home_implied + away_implied + draw_implied
        return (
            home_implied / total,
            away_implied / total,
            draw_implied / total,
        )

    total = home_implied + away_implied
    return home_implied / total, away_implied / total, None


def calculate_vigorish(
    home_odds: float,
    away_odds: float,
    draw_odds: float | None = None,
) -> float:
    """Calculate the vigorish (juice) from odds."""
    implied_probs = calculate_implied_probabilities(home_odds, away_odds, draw_odds)
    total_implied = sum(p for p in implied_probs if p is not None)
    return max(0, (total_implied - 1.0) / total_implied)


def compute_line_movement(
    df: pd.DataFrame,
    match_id_col: str = "match_id",
    odds_col: str = "home_odds",
    time_col: str = "captured_at",
) -> pd.DataFrame:
    """Compute line movement features from odds history."""
    df = df.sort_values(by=[match_id_col, time_col])

    opening = df.groupby(match_id_col)[odds_col].first()
    closing = df.groupby(match_id_col)[odds_col].last()

    movement = pd.DataFrame({
        "opening_odds": opening,
        "closing_odds": closing,
    })
    movement["line_movement"] = movement["closing_odds"] - movement["opening_odds"]

    return movement


def compute_cash_ticket_divergence(
    df: pd.DataFrame,
    match_id_col: str = "match_id",
) -> pd.DataFrame:
    """Compute cash vs ticket divergence."""
    latest = df.sort_values(match_id_col).groupby(match_id_col).last()

    result = pd.DataFrame()
    result["cash_pct_home"] = latest["cash_pct_home"]
    result["ticket_pct_home"] = latest["ticket_pct_home"]
    result["cash_ticket_divergence"] = (
        result["cash_pct_home"] - result["ticket_pct_home"]
    )

    return result


def detect_reverse_line_movement(
    df: pd.DataFrame,
    match_id_col: str = "match_id",
) -> pd.Series:
    """Detect reverse line movement (RLM) - line moved opposite to ticket majority."""
    latest = df.sort_values(match_id_col).groupby(match_id_col).last()

    rlm = (
        (latest["line_movement"] > 0) & (latest["ticket_pct_home"] < 0.5)
    ) | (
        (latest["line_movement"] < 0) & (latest["ticket_pct_home"] > 0.5)
    )

    return rlm.astype(int)


def compute_market_features(
    odds_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute all market/odds-derived features."""
    features = pd.DataFrame()

    if not odds_df.empty:
        latest_odds = odds_df.sort_values("captured_at").groupby("match_id").last()

        features["opening_implied_prob_home"] = (
            odds_df.sort_values("captured_at")
            .groupby("match_id")["home_odds"]
            .first()
            .apply(odds_to_implied_probability)
        )

        features["closing_implied_prob_home"] = latest_odds["home_odds"].apply(
            odds_to_implied_probability
        )

        movement = compute_line_movement(odds_df)
        features["line_movement_spread"] = movement["line_movement"]

        divergence = compute_cash_ticket_divergence(odds_df)
        features["cash_ticket_divergence"] = divergence["cash_ticket_divergence"]

        features["reverse_line_movement"] = detect_reverse_line_movement(odds_df)

    return features


def compute_closing_line_value(
    predicted_prob: float,
    closing_odds: float,
) -> float:
    """Calculate closing line value (CLV)."""
    implied_prob = odds_to_implied_probability(closing_odds)
    return predicted_prob - implied_prob
