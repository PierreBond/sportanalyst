from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import numpy as np


def poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0 or k < 0:
        return 0.0
    return (lam**k * math.exp(-lam)) / math.factorial(k)


def poisson_cdf(k: int, lam: float) -> float:
    cumulative = 0.0
    for i in range(k + 1):
        cumulative += poisson_pmf(i, lam)
    return cumulative


def kelly_fraction(
    odds: float,
    probability: float,
) -> float:
    b = odds - 1
    q = 1 - probability
    f = (b * probability - q) / b
    return max(0.0, min(f, 1.0))


def fractional_kelly(
    odds: float,
    probability: float,
    fraction: float = 0.5,
) -> float:
    full_kelly = kelly_fraction(odds, probability)
    return full_kelly * fraction


def implied_probability(odds: float, vigorish: float = 0.0) -> float:
    if odds <= 0:
        return 0.0
    if vigorish > 0:
        prob = 1 / odds
        adjusted = (1 - vigorish) * prob + vigorish / 3
        return adjusted
    return 1 / odds


def remove_vigorish(
    home_odds: float,
    away_odds: float,
    draw_odds: float | None = None,
) -> tuple[float, float, float | None]:
    if draw_odds is None:
        total = (1 / home_odds) + (1 / away_odds)
        adjusted_home = (1 / home_odds) / total
        adjusted_away = (1 / away_odds) / total
        return adjusted_home, adjusted_away, None
    else:
        total = (1 / home_odds) + (1 / away_odds) + (1 / draw_odds)
        adjusted_home = (1 / home_odds) / total
        adjusted_away = (1 / away_odds) / total
        adjusted_draw = (1 / draw_odds) / total
        return adjusted_home, adjusted_away, adjusted_draw


def brier_score(predictions: list[float], outcomes: list[int]) -> float:
    if len(predictions) != len(outcomes):
        raise ValueError("Predictions and outcomes must have the same length")
    if not predictions:
        return 0.0
    total = sum((p - o) ** 2 for p, o in zip(predictions, outcomes))
    return total / len(predictions)


def brier_score_multiclass(
    predictions: list[dict[str, float]],
    outcomes: list[str],
    classes: list[str],
) -> float:
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
    return (odds * probability) - (1 - probability)


def closing_line_value(
    predicted_prob: float,
    closing_odds: float,
) -> float:
    implied = implied_probability(closing_odds)
    return predicted_prob - implied


def calculate_roi(
    bets: list[dict[str, Any]],
    stake_key: str = "stake",
    payout_key: str = "payout",
) -> float:
    total_stake = sum(bet[stake_key] for bet in bets)
    total_payout = sum(bet[payout_key] for bet in bets)
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
