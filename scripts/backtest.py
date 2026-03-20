from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, accuracy_score, log_loss

from sports_common.config import settings
from sports_common.db import get_async_session
from sports_common.logging import setup_logging, get_logger
from sports_common.utils.math import kelly_fraction

setup_logging("backtest")
logger = get_logger(__name__)


def calculate_brier_score(predictions: np.ndarray, outcomes: np.ndarray) -> float:
    """Calculate Brier score for multi-class predictions.

    Args:
        predictions: Shape (n_samples, n_classes) - predicted probabilities.
        outcomes: Shape (n_samples,) - integer class labels (0, 1, 2).

    Returns:
        Brier score (lower is better).
    """
    n_classes = predictions.shape[1]
    one_hot = np.zeros((len(outcomes), n_classes))
    one_hot[np.arange(len(outcomes)), outcomes] = 1
    return brier_score_loss(one_hot.flatten(), predictions.flatten())


def calculate_accuracy(predictions: np.ndarray, outcomes: np.ndarray) -> float:
    """Calculate accuracy.

    Args:
        predictions: Shape (n_samples, n_classes) - predicted probabilities.
        outcomes: Shape (n_samples,) - integer class labels.

    Returns:
        Accuracy (0-1).
    """
    pred_classes = np.argmax(predictions, axis=1)
    return accuracy_score(outcomes, pred_classes)


def calculate_logloss(predictions: np.ndarray, outcomes: np.ndarray) -> float:
    """Calculate log loss.

    Args:
        predictions: Shape (n_samples, n_classes) - predicted probabilities.
        outcomes: Shape (n_samples,) - integer class labels.

    Returns:
        Log loss.
    """
    return log_loss(outcomes, predictions)


def calculate_roi(
    predictions: np.ndarray,
    outcomes: np.ndarray,
    odds: np.ndarray,
    kelly_fractions: np.ndarray,
) -> dict[str, float]:
    """Calculate ROI metrics for betting strategy.

    Args:
        predictions: Shape (n_samples, n_classes) - predicted probabilities.
        outcomes: Shape (n_samples,) - integer class labels (0=home, 1=draw, 2=away).
        odds: Shape (n_samples, n_classes) - decimal odds for each outcome.
        kelly_fractions: Shape (n_samples,) - Kelly fraction used per bet.

    Returns:
        Dictionary with ROI metrics.
    """
    pred_classes = np.argmax(predictions, axis=1)
    n_bets = len(outcomes)

    total_staked = 0.0
    total_returned = 0.0
    winning_bets = 0

    for i in range(n_bets):
        if kelly_fractions[i] > 0:
            stake = kelly_fractions[i]
            total_staked += stake

            if pred_classes[i] == outcomes[i]:
                winning_bets += 1
                total_returned += stake * odds[i, pred_classes[i]]

    if total_staked == 0:
        return {
            "total_bets": 0,
            "winning_bets": 0,
            "win_rate": 0.0,
            "total_staked": 0.0,
            "total_returned": 0.0,
            "roi": 0.0,
        }

    roi = (total_returned - total_staked) / total_staked

    return {
        "total_bets": n_bets,
        "winning_bets": winning_bets,
        "win_rate": winning_bets / n_bets if n_bets > 0 else 0.0,
        "total_staked": round(total_staked, 2),
        "total_returned": round(total_returned, 2),
        "roi": round(roi * 100, 2),
    }


async def load_backtest_data(
    train_seasons: list[str],
    test_season: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load data for backtesting.

    Args:
        train_seasons: List of season strings for training.
        test_season: Season string for testing.

    Returns:
        Tuple of (train_df, test_df).
    """
    logger.info("loading_backtest_data", train_seasons=train_seasons, test_season=test_season)

    train_data = []
    test_data = []

    for season in train_seasons:
        logger.info("loading_season", season=season, split="train")
        train_data.append(_generate_sample_data(season))

    logger.info("loading_season", season=test_season, split="test")
    test_data.append(_generate_sample_data(test_season))

    train_df = pd.concat(train_data, ignore_index=True)
    test_df = pd.concat(test_data, ignore_index=True)

    logger.info(
        "data_loaded",
        train_samples=len(train_df),
        test_samples=len(test_df),
    )

    return train_df, test_df


def _generate_sample_data(season: str) -> pd.DataFrame:
    """Generate sample data for demonstration.

    In production, this would query the feature store.
    """
    np.random.seed(hash(season) % 2**32)
    n_matches = 100

    data = {
        "match_id": [f"{season}-match-{i}" for i in range(n_matches)],
        "season": [season] * n_matches,
        "home_team": np.random.choice(["Arsenal", "Chelsea", "Liverpool", "Man City"], n_matches),
        "away_team": np.random.choice(["Man United", "Tottenham", "Newcastle", "West Ham"], n_matches),
        "home_goals": np.random.poisson(1.5, n_matches),
        "away_goals": np.random.poisson(1.2, n_matches),
        "rolling_avg_goals_5": np.random.uniform(0.5, 3.0, n_matches),
        "rolling_avg_goals_10": np.random.uniform(0.5, 3.0, n_matches),
        "momentum_xg_slope_5": np.random.uniform(-0.5, 0.5, n_matches),
        "momentum_xg_slope_12": np.random.uniform(-0.3, 0.3, n_matches),
        "is_home": np.random.randint(0, 2, n_matches),
        "rest_days": np.random.randint(2, 14, n_matches),
        "team_avg_acwr": np.random.uniform(0.6, 1.4, n_matches),
        "home_odds": np.random.uniform(1.5, 4.0, n_matches),
        "draw_odds": np.random.uniform(2.5, 5.0, n_matches),
        "away_odds": np.random.uniform(1.5, 4.0, n_matches),
    }

    return pd.DataFrame(data)


def determine_outcome(row: pd.Series) -> int:
    """Determine match outcome class.

    Args:
        row: DataFrame row with home_goals and away_goals.

    Returns:
        0 = home win, 1 = draw, 2 = away win.
    """
    if row["home_goals"] > row["away_goals"]:
        return 0
    elif row["home_goals"] < row["away_goals"]:
        return 2
    return 1


def run_backtest(
    model: Any,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    edge_threshold: float = 0.03,
    kelly_fraction_val: float = 0.25,
) -> dict[str, Any]:
    """Run the full backtest.

    Args:
        model: Trained model with predict_proba method.
        train_df: Training data.
        test_df: Test data.
        edge_threshold: Minimum edge for value bets.
        kelly_fraction_val: Kelly fraction to use.

    Returns:
        Dictionary with all backtest metrics.
    """
    logger.info("running_backtest", test_size=len(test_df))

    feature_cols = [
        "rolling_avg_goals_5",
        "rolling_avg_goals_10",
        "momentum_xg_slope_5",
        "momentum_xg_slope_12",
        "is_home",
        "rest_days",
        "team_avg_acwr",
    ]

    X_train = train_df[feature_cols].values
    X_test = test_df[feature_cols].values

    train_outcomes = train_df.apply(determine_outcome, axis=1).values
    test_outcomes = test_df.apply(determine_outcome, axis=1).values

    logger.info("training_model")
    model.fit(X_train, train_outcomes)

    logger.info("predicting")
    test_predictions = model.predict_proba(X_test)

    logger.info("calculating_metrics")
    brier = calculate_brier_score(test_predictions, test_outcomes)
    accuracy = calculate_accuracy(test_predictions, test_outcomes)
    logloss = calculate_logloss(test_predictions, test_outcomes)

    test_odds = np.column_stack([
        test_df["home_odds"].values,
        test_df["draw_odds"].values,
        test_df["away_odds"].values,
    ])

    implied_probs = 1.0 / test_odds
    edges = test_predictions - implied_probs

    kelly_stakes = np.zeros(len(test_df))
    for i in range(len(test_df)):
        pred_class = np.argmax(test_predictions[i])
        if edges[i, pred_class] >= edge_threshold:
            kelly_stakes[i] = kelly_fraction(
                test_predictions[i, pred_class],
                test_odds[i, pred_class],
                kelly_fraction_val,
            )

    roi_metrics = calculate_roi(
        test_predictions,
        test_outcomes,
        test_odds,
        kelly_stakes,
    )

    closing_line_values = []
    for i in range(len(test_df)):
        pred_class = np.argmax(test_predictions[i])
        clv = test_predictions[i, pred_class] - implied_probs[i, pred_class]
        closing_line_values.append(clv)

    results = {
        "test_season": test_df["season"].iloc[0] if "season" in test_df.columns else "unknown",
        "test_samples": len(test_df),
        "brier_score": round(brier, 4),
        "accuracy": round(accuracy, 4),
        "log_loss": round(logloss, 4),
        "roi_metrics": roi_metrics,
        "avg_closing_line_value": round(np.mean(closing_line_values), 4),
        "positive_clv_pct": round(
            sum(1 for clv in closing_line_values if clv > 0) / len(closing_line_values) * 100, 2
        ),
    }

    logger.info("backtest_complete", results=results)

    return results


def print_results(results: dict[str, Any]) -> None:
    """Print backtest results in a readable format."""
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print(f"Test Season:     {results['test_season']}")
    print(f"Test Samples:    {results['test_samples']}")
    print("-" * 60)
    print("MODEL METRICS")
    print("-" * 60)
    print(f"Brier Score:     {results['brier_score']:.4f}")
    print(f"Accuracy:        {results['accuracy']:.4f}")
    print(f"Log Loss:        {results['log_loss']:.4f}")
    print("-" * 60)
    print("BETTING PERFORMANCE")
    print("-" * 60)
    roi = results["roi_metrics"]
    print(f"Total Bets:      {roi['total_bets']}")
    print(f"Winning Bets:    {roi['winning_bets']}")
    print(f"Win Rate:        {roi['win_rate']:.1%}")
    print(f"Total Staked:    ${roi['total_staked']:.2f}")
    print(f"Total Returned:  ${roi['total_returned']:.2f}")
    print(f"ROI:             {roi['roi']:.2f}%")
    print("-" * 60)
    print("LINE VALUE")
    print("-" * 60)
    print(f"Avg CLV:         {results['avg_closing_line_value']:.4f}")
    print(f"Positive CLV %:  {results['positive_clv_pct']:.1f}%")
    print("=" * 60 + "\n")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run chronological backtest")
    parser.add_argument(
        "--train-seasons",
        nargs="+",
        default=["2021-22", "2022-23", "2023-24"],
        help="Training seasons",
    )
    parser.add_argument("--test-season", default="2024-25", help="Test season")
    parser.add_argument(
        "--edge-threshold",
        type=float,
        default=0.03,
        help="Minimum edge for value bets",
    )
    parser.add_argument(
        "--kelly-fraction",
        type=float,
        default=0.25,
        help="Kelly fraction to use",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON file for results",
    )

    args = parser.parse_args()

    from sklearn.ensemble import RandomForestClassifier

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=6,
        random_state=42,
    )

    train_df, test_df = await load_backtest_data(
        args.train_seasons,
        args.test_season,
    )

    results = run_backtest(
        model,
        train_df,
        test_df,
        edge_threshold=args.edge_threshold,
        kelly_fraction_val=args.kelly_fraction,
    )

    print_results(results)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2))
        logger.info("results_saved", path=str(args.output))


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
