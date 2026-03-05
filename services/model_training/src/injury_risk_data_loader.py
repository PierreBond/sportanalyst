from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from sports_common.logging import get_logger

logger = get_logger(__name__)


class InjuryRiskDataLoader:
    """Data loader for injury risk model training.

    Loads historical biometric data and generates training labels:
    - Positive label (1): Player had injury within 7 days
    - Negative label (0): Player had no injury within 7 days

    Features:
    - ACWR (7/28 day ratio)
    - Rolling HRV (7-day average)
    - Resting HR trend (change over last 7 days)
    - Sleep quality score
    - Cumulative PlayerLoad (season)
    """

    FEATURES = [
        "acwr",
        "hrv_7day_avg",
        "resting_hr_trend",
        "sleep_score",
        "cumulative_player_load",
        "player_age",
        "days_since_last_injury",
        "training_load_7day",
        "recovery_score",
    ]

    def __init__(
        self,
        database_url: str | None = None,
    ) -> None:
        self._database_url = database_url

    def load_training_data(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Load and prepare training data for injury risk model.

        In production, this would query the database.
        For now, generates synthetic training data for demonstration.

        Args:
            start_date: Start of training data period
            end_date: End of training data period

        Returns:
            DataFrame with features and target
        """
        logger.info(
            "loading_injury_risk_data",
            start_date=start_date,
            end_date=end_date,
        )

        data = self._generate_synthetic_data(start_date, end_date)

        df = pd.DataFrame(data)
        df = df.dropna(subset=self.FEATURES)

        logger.info(
            "injury_risk_data_loaded",
            n_samples=len(df),
            positive_rate=df["target"].mean(),
        )

        return df

    def _generate_synthetic_data(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Generate synthetic training data for demonstration."""
        import numpy as np

        days = (end_date - start_date).days
        n_samples = days * 10

        np.random.seed(42)

        data = []

        for i in range(n_samples):
            acwr = np.random.lognormal(mean=0.2, sigma=0.4)
            acwr = min(max(acwr, 0.3), 2.5)

            hrv_7day = np.random.normal(loc=55, scale=15)
            hrv_7day = max(hrv_7day, 20)

            resting_hr_trend = np.random.normal(loc=0, scale=3)

            sleep_score = np.random.beta(a=8, b=4) * 100

            cumulative_load = np.random.lognormal(loc=9, sigma=0.5)

            player_age = np.random.randint(18, 38)

            days_since_injury = np.random.exponential(scale=60)
            days_since_injury = min(days_since_injury, 365)

            training_load_7day = np.random.lognormal(mean=7.5, sigma=0.4)

            recovery_score = np.random.beta(a=6, b=4) * 100

            injury_prob = self._calculate_injury_probability(
                acwr=acwr,
                hrv_7day=hrv_7day,
                resting_hr_trend=resting_hr_trend,
                sleep_score=sleep_score,
                cumulative_load=cumulative_load,
            )

            target = 1 if np.random.random() < injury_prob else 0

            data.append({
                "player_id": f"player_{i % 100}",
                "date": start_date + timedelta(days=np.random.randint(0, days)),
                "acwr": round(acwr, 4),
                "hrv_7day_avg": round(hrv_7day, 2),
                "resting_hr_trend": round(resting_hr_trend, 2),
                "sleep_score": round(sleep_score, 2),
                "cumulative_player_load": round(cumulative_load, 2),
                "player_age": player_age,
                "days_since_last_injury": round(days_since_injury, 1),
                "training_load_7day": round(training_load_7day, 2),
                "recovery_score": round(recovery_score, 2),
                "target": target,
            })

        return data

    def _calculate_injury_probability(
        self,
        acwr: float,
        hrv_7day: float,
        resting_hr_trend: float,
        sleep_score: float,
        cumulative_load: float,
    ) -> float:
        """Calculate synthetic injury probability for label generation."""
        prob = 0.0

        if acwr >= 1.5:
            prob += 0.25
        elif acwr >= 1.3:
            prob += 0.10

        if hrv_7day < 40:
            prob += 0.20
        elif hrv_7day < 50:
            prob += 0.10

        if resting_hr_trend > 5:
            prob += 0.15

        if sleep_score < 50:
            prob += 0.15
        elif sleep_score < 70:
            prob += 0.05

        if cumulative_load > 15000:
            prob += 0.15
        elif cumulative_load > 10000:
            prob += 0.05

        return min(prob, 0.5)

    def prepare_features(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Prepare feature matrix from raw data."""
        features_df = df[self.FEATURES].copy()

        features_df["acwr_squared"] = features_df["acwr"] ** 2
        features_df["hrv_inverse"] = 1 / (features_df["hrv_7day_avg"] + 1)
        features_df["load_per_day"] = (
            features_df["training_load_7day"] / 7
        )

        return features_df

    def chronological_split(
        self,
        df: pd.DataFrame,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Split data chronologically into train/val/test.

        Args:
            df: Input DataFrame with 'date' column
            train_ratio: Fraction for training
            val_ratio: Fraction for validation

        Returns:
            (train_df, val_df, test_df)
        """
        if "date" not in df.columns:
            raise ValueError("DataFrame must have 'date' column")

        df = df.sort_values("date")
        n = len(df)

        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        train_df = df.iloc[:train_end]
        val_df = df.iloc[train_end:val_end]
        test_df = df.iloc[val_end:]

        logger.info(
            "data_split",
            train_size=len(train_df),
            val_size=len(val_df),
            test_size=len(test_df),
            train_date_range=(train_df["date"].min(), train_df["date"].max()),
            test_date_range=(test_df["date"].min(), test_df["date"].max()),
        )

        return train_df, val_df, test_df
