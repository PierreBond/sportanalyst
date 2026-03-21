from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import numpy as np


def poisson_pmf(k: int, lam: float) -> float:
    """Compute the Poisson probability mass function.

    Args:
        k: Number of events (non-negative integer).
        lam: Expected number of events (lambda). Must be positive.

    Returns:
        Probability of observing exactly k events.

    Raises:
        ValueError: If k is negative or lam is not positive.
    """
    if lam <= 0 or k < 0:
        raise ValueError("lam must be positive and k must be non-negative")
    return math.exp(k * math.log(lam) - lam - math.lgamma(k + 1))


def poisson_cdf(k: int, lam: float) -> float:
    """Compute the Poisson cumulative distribution function.

    Args:
        k: Upper bound on number of events (non-negative integer).
        lam: Expected number of events (lambda). Must be positive.

    Returns:
        Probability of observing k or fewer events.

    Raises:
        ValueError: If k is negative or lam is not positive.
    """
    if lam <= 0 or k < 0:
        raise ValueError("lam must be positive and k must be non-negative")
    cumulative = 0.0
    for i in range(k + 1):
        cumulative += poisson_pmf(i, lam)
    return cumulative


def kelly_fraction(odds: float, probability: float) -> float:
    """Calculate the optimal Kelly fraction for a single bet.

    The Kelly fraction determines the proportion of bankroll to wager
    based on the edge available.

    Args:
        odds: Decimal odds (must be greater than 1).
        probability: Estimated probability of winning (0 to 1).

    Returns:
        Optimal fraction of bankroll to bet (0 if no edge exists).
        Capped between 0 and 1.

    Raises:
        ValueError: If odds <= 1 or probability not in [0, 1].
    """
    if odds <= 1:
        raise ValueError("odds must be greater than 1")
    b = odds - 1
    q = 1 - probability
    f = (b * probability - q) / b
    return max(0.0, min(f, 1.0))


def fractional_kelly(
    odds: float,
    probability: float,
    fraction: float = 0.5,
) -> float:
    """Calculate a fractional Kelly bet (conservative variant).

    Args:
        odds: Decimal odds (must be greater than 1).
        probability: Estimated probability of winning (0 to 1).
        fraction: Fraction of full Kelly to use (default 0.5 = half-Kelly).

    Returns:
        Conservative bet fraction. Capped between 0 and 1.

    Raises:
        ValueError: If fraction is not in range (0, 1].
    """
    if fraction <= 0 or fraction > 1:
        raise ValueError("fraction must be in range (0, 1]")
    full_kelly = kelly_fraction(odds, probability)
    return full_kelly * fraction


def implied_probability(odds: float, vigorish: float = 0.0) -> float:
    """Convert decimal odds to implied probability.

    Args:
        odds: Decimal odds (must be positive).
        vigorish: Sportsbook vig/juice as a fraction (default 0 = no vig).

    Returns:
        Implied probability (0 to 1). Accounts for vigorish when provided.

    Raises:
        ValueError: If odds are zero or negative.
    """
    if odds <= 0:
        raise ValueError("odds must be positive")
    prob = 1 / odds
    if vigorish > 0:
        adjusted = (1 - vigorish) * prob + vigorish / 3
        return adjusted
    return prob


def remove_vigorish(
    home_odds: float,
    away_odds: float,
    draw_odds: float | None = None,
) -> tuple[float, float, float | None]:
    """Remove sportsbook vig from moneyline odds.

    Distributes the overround evenly across outcomes to produce
    fair probabilities that sum to 1.0.

    Args:
        home_odds: Decimal odds for home win.
        away_odds: Decimal odds for away win.
        draw_odds: Optional decimal odds for draw (2-way if omitted).

    Returns:
        Tuple of (fair_home_prob, fair_away_prob, fair_draw_prob).
        Draw probability is None for 2-way markets.

    Raises:
        ValueError: If any odds are not positive.
    """
    if draw_odds is None:
        if home_odds <= 0 or away_odds <= 0:
            raise ValueError("All odds must be positive")
        total = (1 / home_odds) + (1 / away_odds)
        adjusted_home = (1 / home_odds) / total
        adjusted_away = (1 / away_odds) / total
        return adjusted_home, adjusted_away, None
    else:
        if home_odds <= 0 or away_odds <= 0 or draw_odds <= 0:
            raise ValueError("All odds must be positive")
        total = (1 / home_odds) + (1 / away_odds) + (1 / draw_odds)
        adjusted_home = (1 / home_odds) / total
        adjusted_away = (1 / away_odds) / total
        adjusted_draw = (1 / draw_odds) / total
        return adjusted_home, adjusted_away, adjusted_draw


def brier_score(predictions: list[float], outcomes: list[int]) -> float:
    """Compute the Brier score for binary predictions.

    Args:
        predictions: List of predicted probabilities (0 to 1).
        outcomes: List of binary outcomes (0 or 1).

    Returns:
        Brier score (0 to 1). Lower is better.

    Raises:
        ValueError: If prediction/outcome lengths differ or predictions
            are outside [0, 1].
    """
    if len(predictions) != len(outcomes):
        raise ValueError("Predictions and outcomes must have the same length")
    if not predictions:
        return 0.0
    for p in predictions:
        if p < 0 or p > 1:
            raise ValueError("Predictions must be between 0 and 1")
    total = sum((p - o) ** 2 for p, o in zip(predictions, outcomes))
    return total / len(predictions)


def brier_score_multiclass(
    predictions: list[dict[str, float]],
    outcomes: list[str],
    classes: list[str],
) -> float:
    """Compute the Brier score for multi-class predictions.

    Args:
        predictions: List of dicts mapping class name to probability.
        outcomes: List of actual class labels.
        classes: List of all class names.

    Returns:
        Multi-class Brier score (0 to 1). Lower is better.

    Raises:
        ValueError: If prediction/outcome lengths differ.
    """
    if len(predictions) != len(outcomes):
        raise ValueError("Predictions and outcomes must have the same length")
    if not predictions:
        return 0.0
    total = 0.0
    for pred, outcome in zip(predictions, outcomes):
        for cls in classes:
            p = pred.get(cls, 0.0)
            o = 1.0 if outcome == cls else 0.0
            total += (p - o) ** 2
    return total / (len(predictions) * len(classes))


def log_loss(
    predictions: list[float],
    outcomes: list[int],
    epsilon: float = 1e-15,
) -> float:
    """Compute log loss (binary cross-entropy) for predictions.

    Args:
        predictions: List of predicted probabilities (0 to 1).
        outcomes: List of binary outcomes (0 or 1).
        epsilon: Small constant for clipping predictions (avoids log(0)).

    Returns:
        Log loss (non-negative). Lower is better.

    Raises:
        ValueError: If prediction/outcome lengths differ.
    """
    if len(predictions) != len(outcomes):
        raise ValueError("Predictions and outcomes must have the same length")
    if not predictions:
        return 0.0
    total = 0.0
    for p, o in zip(predictions, outcomes):
        p = max(epsilon, min(1 - epsilon, p))
        if o == 1:
            total += -math.log(p)
        else:
            total += -math.log(1 - p)
    return total / len(predictions)


def expected_value(
    odds: float,
    probability: float,
) -> float:
    """Calculate expected value of a bet.

    Args:
        odds: Decimal odds.
        probability: Estimated probability of winning (0 to 1).

    Returns:
        Expected value per unit staked. Positive = favorable bet.
    """
    return (odds * probability) - (1 - probability)


def closing_line_value(
    predicted_prob: float,
    closing_odds: float,
) -> float:
    """Compute Closing Line Value (CLV) for a prediction.

    CLV measures how much better your pre-game probability estimate
    was compared to the closing market line.

    Args:
        predicted_prob: Your predicted probability (0 to 1).
        closing_odds: Market closing decimal odds.

    Returns:
        CLV as a probability difference. Positive = beating the line.
    """
    implied = implied_probability(closing_odds)
    return predicted_prob - implied


def calculate_roi(
    bets: list[dict[str, Any]],
    stake_key: str = "stake",
    payout_key: str = "payout",
) -> float:
    """Calculate Return on Investment over a set of bets.

    Args:
        bets: List of bet dicts with stake and payout values.
        stake_key: Key for stake amount in each bet dict.
        payout_key: Key for payout amount in each bet dict.

    Returns:
        ROI as a fraction (e.g., 0.05 = 5% return). 0 if no stakes.
    """
    total_stake = sum(bet[stake_key] for bet in bets)
    total_payout = sum(bet.get(payout_key, 0) for bet in bets)
    if total_stake == 0:
        return 0.0
    return (total_payout - total_stake) / total_stake


def simulate_bankroll(
    initial_bankroll: float,
    bets: list[dict[str, Any]],
    kelly_fraction_val: float = 0.5,
    stake_key: str = "stake",
    payout_key: str = "payout",
    win_key: str = "won",
) -> list[float]:
    """Simulate bankroll growth over a sequence of bets.

    Args:
        initial_bankroll: Starting bankroll amount.
        bets: List of bet dicts with stake, payout, and win_key fields.
        kelly_fraction_val: Fraction of Kelly to bet each wager (default 0.5).
        stake_key: Key for stake amount in each bet dict.
        payout_key: Key for payout amount in each bet dict (decimal odds * stake).
        win_key: Key for whether the bet won (bool).

    Returns:
        List of bankroll values after each bet (starts with initial_bankroll).
    """
    if initial_bankroll <= 0:
        raise ValueError("initial_bankroll must be positive")
    if kelly_fraction_val <= 0 or kelly_fraction_val > 1:
        raise ValueError("kelly_fraction_val must be in (0, 1]")
    bankroll = initial_bankroll
    history = [bankroll]
    for bet in bets:
        stake = bet[stake_key] * kelly_fraction_val * bankroll
        if stake <= 0:
            history.append(bankroll)
            continue
        if bet[win_key]:
            payout = stake * (bet[payout_key] - 1)
            bankroll += payout
        else:
            bankroll -= stake
        history.append(bankroll)
    return history
