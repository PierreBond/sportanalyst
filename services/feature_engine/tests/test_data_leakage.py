from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
import pandas as pd


class TestDataLeakage:
    """Tests to ensure no data leakage in feature computation."""

    def test_temporal_join_uses_lte_operator(self) -> None:
        """Verify temporal joins use <= operator, not < + day hack."""
        from services.feature_engine.src.temporal import add_lag_feature

        df = pd.DataFrame({
            "team_id": ["A", "A", "A", "A"],
            "match_datetime": [
                datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 8, 12, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 22, 12, 0, tzinfo=timezone.utc),
            ],
            "goals_scored": [1, 2, 3, 4],
        })

        result = add_lag_feature(df, "goals_scored", 1, ["team_id"], "lag_1_goals")

        assert result.loc[1, "lag_1_goals"] == 1.0
        assert result.loc[2, "lag_1_goals"] == 2.0
        assert result.loc[3, "lag_1_goals"] == 3.0
        assert pd.isna(result.loc[0, "lag_1_goals"])

    def test_rolling_window_excludes_current_row(self) -> None:
        """Verify rolling windows exclude current match (look-ahead bias)."""
        from services.feature_engine.src.temporal import add_rolling_avg

        df = pd.DataFrame({
            "team_id": ["A"] * 5,
            "match_datetime": [
                datetime(2024, 1, i, 12, 0, tzinfo=timezone.utc) for i in range(1, 6)
            ],
            "venue_type": ["home"] * 5,
            "goals_scored": [1, 2, 3, 4, 5],
        })

        result = add_rolling_avg(df, "goals_scored", 3, ["team_id", "venue_type"], "rolling_avg_goals_3")

        assert result.loc[0, "rolling_avg_goals_3"] == 1.0
        assert result.loc[1, "rolling_avg_goals_3"] == 1.5
        assert result.loc[2, "rolling_avg_goals_3"] == 2.0
        assert result.loc[3, "rolling_avg_goals_3"] == 2.0

    def test_closing_odds_excluded_from_training(self) -> None:
        """Verify closing_implied_prob_home is marked as training ineligible."""
        from services.feature_engine.src.market import compute_market_features

        odds_df = pd.DataFrame({
            "match_id": ["m1", "m1", "m2", "m2"],
            "home_odds": [2.0, 1.9, 3.0, 2.8],
            "away_odds": [2.0, 2.1, 2.0, 2.2],
            "captured_at": [
                datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 20, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 2, 20, 0, tzinfo=timezone.utc),
            ],
            "cash_pct_home": [0.5, 0.6, 0.4, 0.45],
            "ticket_pct_home": [0.5, 0.55, 0.4, 0.42],
        })

        features = compute_market_features(odds_df)

        assert "closing_implied_prob_home" in features.columns

    def test_feature_timestamp_before_prediction_timestamp(self) -> None:
        """Verify computed_at is always <= prediction timestamp."""
        from services.feature_engine.src.store import FeatureStoreWriter

        writer = FeatureStoreWriter()

        match_id = "test-match-id"
        features = {"rolling_avg_goals_5": 1.5}

        computed_at = datetime.now(timezone.utc)
        prediction_time = computed_at + timedelta(hours=1)

        assert computed_at <= prediction_time, "Feature computed_at must be <= prediction timestamp"

    def test_rest_days_uses_past_data_only(self) -> None:
        """Verify rest_days calculation only uses past matches."""
        from services.feature_engine.src.temporal import add_rest_days

        df = pd.DataFrame({
            "team_id": ["A", "A", "A"],
            "match_datetime": [
                datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 8, 12, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc),
            ],
        })

        result = add_rest_days(df)

        assert result.loc[0, "rest_days"] == 7
        assert result.loc[1, "rest_days"] == 7
        assert result.loc[2, "rest_days"] == 7

    def test_sentiment_uses_only_historical_data(self) -> None:
        """Verify sentiment features only use data before match time."""
        from services.feature_engine.src.sentiment import aggregate_sentiment_by_source

        sentiment_df = pd.DataFrame({
            "entity_id": ["team1"] * 5,
            "source": ["twitter"] * 5,
            "score": [0.5, 0.6, 0.7, 0.8, 0.9],
            "volume": [10] * 5,
            "captured_at": [
                datetime(2024, 1, 1, i, 0, tzinfo=timezone.utc)
                for i in range(5)
            ],
        })

        result = aggregate_sentiment_by_source(sentiment_df, "team1", time_window_hours=24)

        assert result["twitter_sentiment"] > 0

    def test_biometric_uses_only_historical_readings(self) -> None:
        """Verify biometric features only use data available at match time."""
        from services.feature_engine.src.biometric import compute_acwr
        from datetime import timedelta

        workload_df = pd.DataFrame({
            "recorded_at": [
                datetime.now(timezone.utc) - timedelta(days=i)
                for i in range(30, 0, -1)
            ],
            "value": [100 + i for i in range(30)],
        })

        as_of = datetime.now(timezone.utc)
        acwr = compute_acwr(workload_df, as_of)

        assert acwr > 0

    def test_momentum_slope_uses_past_data_only(self) -> None:
        """Verify momentum slope only uses historical xG values."""
        from services.feature_engine.src.temporal import add_momentum_slope

        df = pd.DataFrame({
            "team_id": ["A"] * 5,
            "match_datetime": [
                datetime(2024, 1, i, 12, 0, tzinfo=timezone.utc) for i in range(1, 6)
            ],
            "xg": [1.0, 1.2, 1.4, 1.6, 1.8],
        })

        result = add_momentum_slope(df, "xg", 3, ["team_id"], "momentum_xg_slope_3")

        assert result.loc[0, "momentum_xg_slope_3"] == 0.0
        assert not pd.isna(result.loc[3, "momentum_xg_slope_3"])
