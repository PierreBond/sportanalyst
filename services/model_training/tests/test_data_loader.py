from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from services.model_training.src.data_loader import DataLoader


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Create a sample DataFrame for testing."""
    return pd.DataFrame({
        "match_id": [f"m{i}" for i in range(20)],
        "scheduled_at": pd.date_range("2023-01-01", periods=20, freq="7D", tz="UTC"),
        "league": ["EPL"] * 20,
        "season": ["2022-23"] * 10 + ["2023-24"] * 5 + ["2024-25"] * 5,
        "home_team_id": ["t1"] * 20,
        "away_team_id": ["t2"] * 20,
        "home_score": [2, 1, 0, 3, 1, 2, 0, 1, 2, 3, 1, 2, 0, 1, 3, 2, 1, 0, 2, 1],
        "away_score": [1, 1, 2, 0, 1, 0, 1, 2, 1, 0, 2, 1, 0, 2, 1, 0, 1, 3, 0, 2],
        "rolling_avg_goals_5": [1.5] * 20,
        "rest_days": [7.0] * 20,
    })


@pytest.fixture
def loader() -> DataLoader:
    """Create a DataLoader instance."""
    return DataLoader()


class TestChronologicalSplit:
    """Tests for DataLoader.chronological_split — critical anti-leakage mechanism."""

    def test_split_by_season(self, loader: DataLoader, sample_df: pd.DataFrame) -> None:
        train, val, test = loader.chronological_split(
            sample_df,
            train_seasons=["2022-23"],
            val_season="2023-24",
            test_season="2024-25",
        )
        assert len(train) == 10
        assert len(val) == 5
        assert len(test) == 5

    def test_split_preserves_chronological_order(self, loader: DataLoader, sample_df: pd.DataFrame) -> None:
        train, val, test = loader.chronological_split(
            sample_df,
            train_seasons=["2022-23"],
            val_season="2023-24",
            test_season="2024-25",
        )
        if not train.empty and not val.empty:
            assert train["scheduled_at"].max() <= val["scheduled_at"].min()
        if not val.empty and not test.empty:
            assert val["scheduled_at"].max() <= test["scheduled_at"].min()

    def test_split_by_ratio_is_chronological(self, loader: DataLoader, sample_df: pd.DataFrame) -> None:
        train, val, test = loader.chronological_split(sample_df, train_ratio=0.6)
        assert len(train) == 12
        if not train.empty and not val.empty:
            assert train["scheduled_at"].max() <= val["scheduled_at"].min()
        if not val.empty and not test.empty:
            assert val["scheduled_at"].max() <= test["scheduled_at"].min()

    def test_no_data_leakage_across_splits(self, loader: DataLoader, sample_df: pd.DataFrame) -> None:
        train, val, test = loader.chronological_split(
            sample_df,
            train_seasons=["2022-23"],
            val_season="2023-24",
            test_season="2024-25",
        )
        train_ids = set(train["match_id"])
        val_ids = set(val["match_id"])
        test_ids = set(test["match_id"])
        assert train_ids.isdisjoint(val_ids)
        assert train_ids.isdisjoint(test_ids)
        assert val_ids.isdisjoint(test_ids)

    def test_never_uses_random_split(self, loader: DataLoader, sample_df: pd.DataFrame) -> None:
        """Run split twice; results must be identical (no randomness)."""
        train1, val1, test1 = loader.chronological_split(sample_df, train_ratio=0.7)
        train2, val2, test2 = loader.chronological_split(sample_df, train_ratio=0.7)
        pd.testing.assert_frame_equal(train1, train2)
        pd.testing.assert_frame_equal(val1, val2)
        pd.testing.assert_frame_equal(test1, test2)


class TestImputeMissingValues:
    """Tests for DataLoader.impute_missing_values."""

    def test_imputes_nan_with_median(self, loader: DataLoader) -> None:
        df = pd.DataFrame({
            "match_id": ["m1", "m2", "m3"],
            "scheduled_at": pd.date_range("2024-01-01", periods=3, freq="D"),
            "league": ["EPL"] * 3,
            "season": ["2024"] * 3,
            "home_team_id": ["t1"] * 3,
            "away_team_id": ["t2"] * 3,
            "home_score": [1, 2, 3],
            "away_score": [0, 1, 2],
            "rolling_avg_goals_5": [1.0, None, 3.0],
        })
        result = loader.impute_missing_values(df)
        assert result["rolling_avg_goals_5"].isna().sum() == 0

    def test_empty_df_returns_empty(self, loader: DataLoader) -> None:
        result = loader.impute_missing_values(pd.DataFrame())
        assert result.empty


class TestFilterFeatures:
    """Tests for DataLoader.filter_features."""

    def test_excludes_closing_implied_prob(self, loader: DataLoader) -> None:
        df = pd.DataFrame({
            "match_id": ["m1"],
            "scheduled_at": [datetime(2024, 1, 1, tzinfo=timezone.utc)],
            "league": ["EPL"],
            "season": ["2024"],
            "home_team_id": ["t1"],
            "away_team_id": ["t2"],
            "home_score": [1],
            "away_score": [0],
            "rolling_avg_goals_5": [1.5],
            "closing_implied_prob_home": [0.55],
        })
        result = loader.filter_features(df)
        assert "closing_implied_prob_home" not in result.columns
        assert "rolling_avg_goals_5" in result.columns

    def test_empty_df(self, loader: DataLoader) -> None:
        result = loader.filter_features(pd.DataFrame())
        assert result.empty


class TestCreateTarget:
    """Tests for DataLoader.create_target."""

    def test_home_win(self, loader: DataLoader) -> None:
        df = pd.DataFrame({"home_score": [3], "away_score": [1]})
        target = loader.create_target(df)
        assert target.iloc[0] == 0

    def test_away_win(self, loader: DataLoader) -> None:
        df = pd.DataFrame({"home_score": [0], "away_score": [2]})
        target = loader.create_target(df)
        assert target.iloc[0] == 2

    def test_draw(self, loader: DataLoader) -> None:
        df = pd.DataFrame({"home_score": [1], "away_score": [1]})
        target = loader.create_target(df)
        assert target.iloc[0] == 1

    def test_empty_df(self, loader: DataLoader) -> None:
        target = loader.create_target(pd.DataFrame())
        assert target.empty
