from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
import structlog
from sqlalchemy import select, and_

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from alembic.models import Match, FeatureStore
from sports_common.config import settings
from sports_common.db import get_async_session
from sports_common.logging import get_logger

logger = get_logger(__name__)

EXCLUDED_FEATURES = {"closing_implied_prob_home"}


class DataLoader:
    """Loads and prepares training data from feature store.

    Implements chronological train/val/test splits per RULE-T3.
    Filters features marked as training_ineligible.
    """

    def __init__(
        self,
        config_path: str | Path | None = None,
    ) -> None:
        self._config = self._load_feature_config(config_path)
        self._excluded_features = self._get_excluded_features()

    def _load_feature_config(self, config_path: str | Path | None) -> dict[str, Any]:
        """Load feature configuration from YAML."""
        if config_path is None:
            config_path = (
                Path(__file__).parent.parent / "feature_engine" / "configs" / "features.yaml"
            )

        if Path(config_path).exists():
            try:
                import yaml
            except ImportError:
                raise RuntimeError(
                    "PyYAML is required for loading feature config. "
                    "Install it with: pip install pyyaml"
                )
            with open(config_path) as f:
                return yaml.safe_load(f)
        return {}

    def _get_excluded_features(self) -> set[str]:
        """Get features excluded from training."""
        excluded = set(EXCLUDED_FEATURES)

        if "features" in self._config:
            for feature in self._config["features"]:
                if not feature.get("training_eligible", True):
                    excluded.add(feature["name"])

        logger.info("excluded_features", count=len(excluded), features=list(excluded))
        return excluded

    async def load_features(
        self,
        leagues: list[str] | None = None,
        seasons: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Load features from feature store with optional filters."""
        async with get_async_session() as session:
            query = select(FeatureStore, Match).join(Match, FeatureStore.match_id == Match.match_id)

            conditions = []
            if leagues:
                conditions.append(Match.league.in_(leagues))
            if seasons:
                conditions.append(Match.season.in_(seasons))
            if start_date:
                conditions.append(Match.scheduled_at >= start_date)
            if end_date:
                conditions.append(Match.scheduled_at <= end_date)

            if conditions:
                query = query.where(and_(*conditions))

            result = await session.execute(query)
            rows = result.all()

        if not rows:
            logger.warning("no_features_found")
            return pd.DataFrame()

        data = []
        for feature_store, match in rows:
            row = {
                "match_id": str(feature_store.match_id),
                "scheduled_at": match.scheduled_at,
                "league": match.league,
                "season": match.season,
                "home_team_id": str(match.home_team_id) if match.home_team_id else None,
                "away_team_id": str(match.away_team_id) if match.away_team_id else None,
                "home_score": match.home_score,
                "away_score": match.away_score,
            }

            features = feature_store.features
            for key, value in features.items():
                if key not in self._excluded_features:
                    row[key] = value

            data.append(row)

        df = pd.DataFrame(data)
        logger.info("features_loaded", rows=len(df))
        return df

    def filter_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter out training-ineligible features."""
        if df.empty:
            return df

        feature_cols = [
            c
            for c in df.columns
            if c
            not in [
                "match_id",
                "scheduled_at",
                "league",
                "season",
                "home_team_id",
                "away_team_id",
                "home_score",
                "away_score",
            ]
        ]

        filtered_cols = [c for c in feature_cols if c not in self._excluded_features]

        result = df[
            [
                "match_id",
                "scheduled_at",
                "league",
                "season",
                "home_team_id",
                "away_team_id",
                "home_score",
                "away_score",
            ]
            + filtered_cols
        ].copy()

        logger.info(
            "features_filtered",
            original=len(feature_cols),
            filtered=len(filtered_cols),
            excluded=len(feature_cols) - len(filtered_cols),
        )
        return result

    def impute_missing_values(
        self,
        df: pd.DataFrame,
        strategy: str = "median",
    ) -> pd.DataFrame:
        """Impute missing values with league-season median."""
        if df.empty:
            return df

        result = df.copy()

        feature_cols = [
            c
            for c in df.columns
            if c
            not in [
                "match_id",
                "scheduled_at",
                "league",
                "season",
                "home_team_id",
                "away_team_id",
                "home_score",
                "away_score",
            ]
        ]

        for col in feature_cols:
            if result[col].isna().any():
                if strategy == "median":
                    median_val = result[col].median()
                    if pd.isna(median_val):
                        median_val = 0.0
                    result[col] = result[col].fillna(median_val)
                    logger.info(
                        "imputed_missing_values",
                        column=col,
                        strategy=strategy,
                        imputed_count=result[col].isna().sum(),
                    )

        return result

    def create_target(self, df: pd.DataFrame) -> pd.Series:
        """Create target variable: home_win | draw | away_win."""
        if df.empty:
            return pd.Series(dtype=str)

        def get_result(row):
            if pd.isna(row["home_score"]) or pd.isna(row["away_score"]):
                return None
            if row["home_score"] > row["away_score"]:
                return "home_win"
            elif row["home_score"] < row["away_score"]:
                return "away_win"
            else:
                return "draw"

        return df.apply(get_result, axis=1)

    def chronological_split(
        self,
        df: pd.DataFrame,
        train_seasons: list[str] | None = None,
        val_season: str | None = None,
        test_season: str | None = None,
        train_ratio: float = 0.7,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Split data chronologically for training.

        Args:
            df: Input DataFrame with 'season' column
            train_seasons: List of seasons for training (e.g., ["2021-22", "2022-23"])
            val_season: Season for validation (e.g., "2023-24")
            test_season: Season for testing (e.g., "2024-25")
            train_ratio: Ratio for random-free chronological split if no seasons specified

        Returns:
            (train_df, val_df, test_df)
        """
        df = df.sort_values("scheduled_at").reset_index(drop=True)

        if train_seasons or val_season or test_season:
            train_df = df[df["season"].isin(train_seasons)] if train_seasons else pd.DataFrame()
            val_df = df[df["season"] == val_season] if val_season else pd.DataFrame()
            test_df = df[df["season"] == test_season] if test_season else pd.DataFrame()
        else:
            n = len(df)
            train_end = int(n * train_ratio)
            val_end = int(n * (train_ratio + (1 - train_ratio) / 2))

            train_df = df.iloc[:train_end]
            val_df = df.iloc[train_end:val_end]
            test_df = df.iloc[val_end:]

        logger.info(
            "chronological_split",
            train=len(train_df),
            val=len(val_df),
            test=len(test_df),
        )

        return train_df, val_df, test_df

    def prepare_training_data(
        self,
        leagues: list[str] | None = None,
        seasons: list[str] | None = None,
        train_seasons: list[str] | None = None,
        val_season: str | None = None,
        test_season: str | None = None,
        impute: bool = True,
    ) -> tuple[
        pd.DataFrame,
        pd.Series | None,
        pd.DataFrame,
        pd.Series | None,
        pd.DataFrame,
        pd.Series | None,
    ]:
        """Load and prepare training data with chronological split.

        Returns:
            (X_train, y_train, X_val, y_val, X_test, y_test)
        """
        import asyncio

        df = asyncio.run(self.load_features(leagues=leagues, seasons=seasons))

        if df.empty:
            logger.warning("no_data_loaded")
            return (pd.DataFrame(), None, pd.DataFrame(), None, pd.DataFrame(), None)

        df = self.filter_features(df)

        if impute:
            df = self.impute_missing_values(df)

        train_df, val_df, test_df = self.chronological_split(
            df,
            train_seasons=train_seasons,
            val_season=val_season,
            test_season=test_season,
        )

        feature_cols = [
            c
            for c in df.columns
            if c
            not in [
                "match_id",
                "scheduled_at",
                "league",
                "season",
                "home_team_id",
                "away_team_id",
                "home_score",
                "away_score",
            ]
        ]

        y_train = self.create_target(train_df) if not train_df.empty else None
        y_val = self.create_target(val_df) if not val_df.empty else None
        y_test = self.create_target(test_df) if not test_df.empty else None

        X_train = train_df[feature_cols] if not train_df.empty else pd.DataFrame()
        X_val = val_df[feature_cols] if not val_df.empty else pd.DataFrame()
        X_test = test_df[feature_cols] if not test_df.empty else pd.DataFrame()

        return X_train, y_train, X_val, y_val, X_test, y_test

    def get_feature_names(self, df: pd.DataFrame) -> list[str]:
        """Get list of feature column names."""
        return [
            c
            for c in df.columns
            if c
            not in [
                "match_id",
                "scheduled_at",
                "league",
                "season",
                "home_team_id",
                "away_team_id",
                "home_score",
                "away_score",
            ]
        ]


async def main() -> None:
    """Test data loader."""
    loader = DataLoader()

    df = await loader.load_features(seasons=["2021-22", "2022-23", "2023-24"])

    if not df.empty:
        df = loader.filter_features(df)
        df = loader.impute_missing_values(df)

        train, val, test = loader.chronological_split(
            df,
            train_seasons=["2021-22", "2022-23"],
            val_season="2023-24",
        )

        print(f"Train: {len(train)}, Val: {len(val)}, Test: {len(test)}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
