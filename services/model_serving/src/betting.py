from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import uuid4

import numpy as np

from sports_common.schemas.predictions import ValueBet


class BetSelection(str, Enum):
    """Possible bet selections for a match outcome."""

    HOME_WIN = "home_win"
    DRAW = "draw"
    AWAY_WIN = "away_win"


EDGE_THRESHOLD = 0.03
MAX_EXPOSURE_PER_MATCH = 0.05
MAX_DAILY_EXPOSURE = 0.15


def implied_probability(decimal_odds: float) -> float:
    """Convert decimal odds to implied probability.

    Args:
        decimal_odds: Decimal odds offered by the book (e.g., 2.50).

    Returns:
        Implied probability as a float between 0 and 1.
    """
    if decimal_odds <= 1.0:
        raise ValueError(f"Decimal odds must be greater than 1.0, got {decimal_odds}")
    return round(1.0 / decimal_odds, 6)


def kelly_fraction(
    prob_win: float,
    decimal_odds: float,
    fraction: float = 0.25,
) -> float:
    """Compute fractional Kelly stake.

    Args:
        prob_win: Model's estimated probability of winning.
        decimal_odds: Decimal odds offered by the book (e.g., 2.50).
        fraction: Kelly fraction to use (0.25 = quarter Kelly). Default conservative.

    Returns:
        Fraction of bankroll to wager. Returns 0.0 if no edge.
    """
    if decimal_odds <= 1.0:
        return 0.0

    b = decimal_odds - 1.0
    q = 1.0 - prob_win
    edge = (b * prob_win - q) / b

    if edge <= 0:
        return 0.0

    return round(edge * fraction, 6)


def remove_vig(
    home_odds: float, away_odds: float, draw_odds: float | None = None
) -> tuple[float, float, float | None]:
    """Remove vigorish to get true probabilities.

    Args:
        home_odds: Decimal odds for home win.
        away_odds: Decimal odds for away win.
        draw_odds: Optional decimal odds for draw.

    Returns:
        Tuple of true probabilities (home, away[, draw]).
    """
    probs_raw = [1.0 / home_odds, 1.0 / away_odds]
    if draw_odds is not None:
        probs_raw.append(1.0 / draw_odds)

    total = sum(probs_raw)
    result = tuple(round(p / total, 6) for p in probs_raw)

    if draw_odds is not None:
        return result[0], result[1], result[2]
    return result[0], result[1], None


class BettingEngine:
    """Engine for detecting value bets and calculating stakes."""

    def __init__(
        self,
        edge_threshold: float = EDGE_THRESHOLD,
        max_exposure_per_match: float = MAX_EXPOSURE_PER_MATCH,
        max_daily_exposure: float = MAX_DAILY_EXPOSURE,
        kelly_fraction: float = 0.25,
    ) -> None:
        """Initialize the betting engine.

        Args:
            edge_threshold: Minimum edge required to consider a bet (default 3%).
            max_exposure_per_match: Maximum percentage of bankroll per match (default 5%).
            max_daily_exposure: Maximum percentage of bankroll per day (default 15%).
            kelly_fraction: Fraction of Kelly to use (default 0.25 = quarter Kelly).
        """
        self.edge_threshold = edge_threshold
        self.max_exposure_per_match = max_exposure_per_match
        self.max_daily_exposure = max_daily_exposure
        self.kelly_fraction = kelly_fraction

    def detect_value_bet(
        self,
        match_id: str,
        selection: BetSelection,
        model_prob: float,
        decimal_odds: float,
        sportsbook: str,
    ) -> ValueBet | None:
        """Detect if a bet represents value.

        Args:
            match_id: Unique match identifier.
            selection: The outcome being bet on.
            model_prob: Model's estimated probability.
            decimal_odds: Decimal odds from sportsbook.
            sportsbook: Name of the sportsbook.

        Returns:
            ValueBet if value detected, None otherwise.
        """
        implied_prob = implied_probability(decimal_odds)
        edge = model_prob - implied_prob

        if edge < self.edge_threshold:
            return None

        kelly_stake = kelly_fraction(
            model_prob, decimal_odds, self.kelly_fraction
        )

        kelly_stake = min(kelly_stake, self.max_exposure_per_match)

        return ValueBet(
            match_id=match_id,
            model_name="xgboost_match_outcome",
            sportsbook=sportsbook,
            market_type="match_result",
            selection=selection.value,
            model_probability=model_prob,
            odds=decimal_odds,
            expected_value=edge,
            stake=kelly_stake * 100,
        )

    def evaluate_bets(
        self,
        match_id: str,
        probabilities: dict[str, float],
        odds: dict[str, float],
        sportsbook: str,
    ) -> list[ValueBet]:
        """Evaluate all three outcomes for value bets.

        Args:
            match_id: Unique match identifier.
            probabilities: Dict with 'home_win', 'draw', 'away_win' probabilities.
            odds: Dict with 'home_win', 'draw', 'away_win' decimal odds.
            sportsbook: Name of the sportsbook.

        Returns:
            List of ValueBet objects found (can be empty).
        """
        value_bets = []

        selection_map = {
            "home_win": BetSelection.HOME_WIN,
            "draw": BetSelection.DRAW,
            "away_win": BetSelection.AWAY_WIN,
        }

        for outcome, selection in selection_map.items():
            if outcome in probabilities and outcome in odds:
                bet = self.detect_value_bet(
                    match_id=match_id,
                    selection=selection,
                    model_prob=probabilities[outcome],
                    decimal_odds=odds[outcome],
                    sportsbook=sportsbook,
                )
                if bet:
                    value_bets.append(bet)

        return value_bets

    def calculate_closing_line_value(
        self,
        model_prob: float,
        closing_odds: float,
    ) -> float:
        """Calculate Closing Line Value (CLV).

        Args:
            model_prob: Model's estimated probability.
            closing_odds: Closing line odds from sportsbook.

        Returns:
            CLV as a float. Positive means the bet had positive expected value.
        """
        closing_implied = implied_probability(closing_odds)
        return model_prob - closing_implied

    def filter_by_daily_exposure(
        self,
        value_bets: list[ValueBet],
        current_daily_exposure: float,
    ) -> list[ValueBet]:
        """Filter value bets by daily exposure limit.

        Args:
            value_bets: List of detected value bets.
            current_daily_exposure: Current daily exposure as percentage.

        Returns:
            Filtered list of ValueBet objects that fit within daily limit.
        """
        remaining_budget = self.max_daily_exposure - current_daily_exposure
        if remaining_budget <= 0:
            return []

        filtered = []
        total_stake = 0.0

        for bet in value_bets:
            bet_stake = (bet.stake or 0.0) / 100
            if total_stake + bet_stake <= remaining_budget:
                filtered.append(bet)
                total_stake += bet_stake

        return filtered
