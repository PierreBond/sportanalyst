from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd


def aggregate_sentiment_by_source(
    sentiment_df: pd.DataFrame,
    entity_id: str,
    time_window_hours: int = 24,
    as_of: datetime | None = None,
) -> dict[str, float]:
    """Aggregate sentiment scores by source within a time window.

    Args:
        sentiment_df: DataFrame with columns [entity_id, source, score, captured_at]
        entity_id: The entity (team/player) to aggregate for
        time_window_hours: Time window in hours
        as_of: Reference timestamp for the lookback window. Defaults to UTC now
            if not provided. For training data, this MUST be the match_datetime
            to avoid temporal leakage (RULE-24/RULE-F1).

    Returns:
        Dict of source -> aggregated sentiment score
    """
    if as_of is None:
        as_of = datetime.now(timezone.utc)

    cutoff = as_of - timedelta(hours=time_window_hours)

    filtered = sentiment_df[
        (sentiment_df["entity_id"] == entity_id)
        & (sentiment_df["captured_at"] >= cutoff)
    ]

    if filtered.empty:
        return {
            "twitter_sentiment": 0.0,
            "reddit_sentiment": 0.0,
            "news_sentiment": 0.0,
            "total_volume": 0,
        }

    result = {"total_volume": int(filtered["volume"].sum())}

    for source in ["twitter", "reddit", "news"]:
        source_data = filtered[filtered["source"] == source]
        if not source_data.empty:
            result[f"{source}_sentiment"] = float(source_data["score"].mean())
        else:
            result[f"{source}_sentiment"] = 0.0

    return result


def compute_sentiment_features(
    sentiment_df: pd.DataFrame,
    entity_ids: list[str],
    time_window_hours: int = 24,
    as_of: datetime | None = None,
) -> pd.DataFrame:
    """Compute sentiment features for multiple entities.

    Args:
        sentiment_df: DataFrame with sentiment scores
        entity_ids: List of entity IDs to compute features for
        time_window_hours: Time window in hours
        as_of: Reference timestamp for the lookback window (RULE-24).

    Returns:
        DataFrame with sentiment features per entity
    """
    features = []

    for entity_id in entity_ids:
        agg = aggregate_sentiment_by_source(
            sentiment_df, entity_id, time_window_hours, as_of=as_of
        )
        agg["entity_id"] = entity_id
        features.append(agg)

    return pd.DataFrame(features)


def weighted_sentiment(
    twitter_sentiment: float,
    reddit_sentiment: float,
    news_sentiment: float,
    weights: dict[str, float] | None = None,
) -> float:
    """Compute weighted average of sentiment from different sources.

    Default weights: Twitter 0.3, Reddit 0.3, News 0.4
    """
    if weights is None:
        weights = {
            "twitter": 0.3,
            "reddit": 0.3,
            "news": 0.4,
        }

    return (
        weights["twitter"] * twitter_sentiment
        + weights["reddit"] * reddit_sentiment
        + weights["news"] * news_sentiment
    )


def sentiment_trend(
    sentiment_df: pd.DataFrame,
    entity_id: str,
    source: str,
    window_size: int = 5,
    as_of: datetime | None = None,
) -> float:
    """Calculate sentiment trend over recent time windows."""
    if as_of is None:
        as_of = datetime.now(timezone.utc)

    cutoff = as_of - timedelta(hours=24)

    filtered = sentiment_df[
        (sentiment_df["entity_id"] == entity_id)
        & (sentiment_df["source"] == source)
        & (sentiment_df["captured_at"] >= cutoff)
    ]

    if filtered.empty or len(filtered) < 2:
        return 0.0

    filtered = filtered.sort_values("captured_at").tail(window_size)

    if len(filtered) < 2:
        return 0.0

    first = filtered.iloc[0]["score"]
    last = filtered.iloc[-1]["score"]

    return last - first
