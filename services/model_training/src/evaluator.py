from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
)


def compute_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Compute accuracy score."""
    return accuracy_score(y_true, y_pred)


def compute_brier_score(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_classes: int = 3,
) -> float:
    """Compute Brier score for multiclass predictions."""
    return brier_score_loss(y_true, y_prob, multi_label="ovr")


def compute_log_loss(
    y_true: np.ndarray,
    y_prob: np.ndarray,
) -> float:
    """Compute log loss."""
    return log_loss(y_true, y_prob)


def compute_f1_score(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    average: str = "macro",
) -> float:
    """Compute F1 score."""
    return f1_score(y_true, y_pred, average=average)


def compute_closing_line_value(
    predicted_probabilities: np.ndarray,
    closing_odds: np.ndarray,
    actual_outcomes: np.ndarray,
) -> np.ndarray:
    """Compute Closing Line Value for each prediction."""
    implied_probs = 1.0 / closing_odds
    clv = predicted_probabilities - implied_probs
    return clv


def compute_roi(
    bets: list[dict[str, Any]],
    stake_key: str = "stake",
    payout_key: str = "payout",
) -> float:
    """Compute Return on Investment."""
    total_stake = sum(bet[stake_key] for bet in bets)
    total_payout = sum(bet.get(payout_key, 0) for bet in bets)
    if total_stake == 0:
        return 0.0
    return (total_payout - total_stake) / total_stake


def compute_calibration_curve(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute calibration curve for reliability diagram."""
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    true_probs = []
    pred_probs = []

    for i in range(n_bins):
        mask = (y_prob >= bin_edges[i]) & (y_prob < bin_edges[i + 1])
        if mask.sum() > 0:
            true_probs.append(y_true[mask].mean())
            pred_probs.append(y_prob[mask].mean())

    return np.array(pred_probs), np.array(true_probs)


def evaluate_model(
    model: Any,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    closing_odds: np.ndarray | None = None,
) -> dict[str, float]:
    """Comprehensive model evaluation.

    Returns dict with: accuracy, brier_score, log_loss, f1_macro, f1_weighted
    """
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)

    results = {
        "accuracy": compute_accuracy(y_test.values, y_pred),
        "brier_score": compute_brier_score(y_test.values, y_prob),
        "log_loss": compute_log_loss(y_test.values, y_prob),
        "f1_macro": compute_f1_score(y_test.values, y_pred, average="macro"),
        "f1_weighted": compute_f1_score(y_test.values, y_pred, average="weighted"),
    }

    if closing_odds is not None:
        home_probs = y_prob[:, 0]
        clv = compute_closing_line_value(home_probs, closing_odds, y_test.values)
        results["mean_clv"] = float(clv.mean())

    return results


def compute_all_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: np.ndarray,
) -> dict[str, float]:
    """Compute all standard metrics."""
    return {
        "accuracy": compute_accuracy(y_true, y_pred),
        "brier_score": compute_brier_score(y_true, y_prob),
        "log_loss": compute_log_loss(y_true, y_prob),
        "f1_macro": compute_f1_score(y_true, y_pred, average="macro"),
        "f1_weighted": compute_f1_score(y_true, y_pred, average="weighted"),
    }
