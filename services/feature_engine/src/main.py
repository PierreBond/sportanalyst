from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any

import structlog
from pyspark.sql import SparkSession, DataFrame, Window
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    DoubleType,
    IntegerType,
    TimestampType,
)

from sports_common.config import settings
from sports_common.kafka_client import AsyncKafkaConsumer

from temporal import (
    add_rolling_avg,
    add_rolling_std,
    add_momentum_slope,
    add_lag_feature,
    add_rest_days,
)
from market import (
    compute_market_features,
    odds_to_implied_probability,
)
from biometric import aggregate_team_biometrics
from sentiment import compute_sentiment_features
from store import FeatureStoreWriter

logger = structlog.get_logger(__name__)

KAFKA_RAW_MATCH_EVENTS = "raw.match-events"
KAFKA_RAW_ODDS = "raw.odds-updates"
KAFKA_PROCESSED_SENTIMENT = "processed.sentiment"
KAFKA_PROCESSED_BIOMETRIC = "processed.biometric-features"
KAFKA_OUTPUT_FEATURES = "processed.features"

ODDS_SCHEMA = StructType(
    [
        StructField("match_id", StringType(), True),
        StructField("home_odds", DoubleType(), True),
        StructField("away_odds", DoubleType(), True),
        StructField("draw_odds", DoubleType(), True),
        StructField("captured_at", TimestampType(), True),
        StructField("cash_pct_home", DoubleType(), True),
        StructField("ticket_pct_home", DoubleType(), True),
    ]
)

SENTIMENT_SCHEMA = StructType(
    [
        StructField("entity_id", StringType(), True),
        StructField("source", StringType(), True),
        StructField("score", DoubleType(), True),
        StructField("volume", DoubleType(), True),
        StructField("captured_at", TimestampType(), True),
    ]
)

BIOMETRIC_SCHEMA = StructType(
    [
        StructField("team_id", StringType(), True),
        StructField("acwr", DoubleType(), True),
        StructField("hrv", DoubleType(), True),
        StructField("injury_risk", DoubleType(), True),
    ]
)

# Window sizes for rolling feature computation (RULE-10)
ROLLING_WINDOW_5_START = -4
ROLLING_WINDOW_5_END = -1
ROLLING_WINDOW_10_START = -9
ROLLING_WINDOW_10_END = -1
TICKET_PCT_HOME_THRESHOLD = 0.5


def create_spark_session(app_name: str = "feature-engine") -> SparkSession:
    """Create and configure Spark session."""
    spark = (
        SparkSession.builder.appName(app_name)
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark


def load_matches_from_db(spark: SparkSession) -> DataFrame:
    """Load matches from Postgres."""
    jdbc_url = settings.database_url.replace("postgresql+asyncpg", "postgresql")
    df = (
        spark.read.format("jdbc")
        .option("url", jdbc_url)
        .option("dbtable", "matches")
        .option("user", os.getenv("POSTGRES_USER", "postgres"))
        .option("password", os.getenv("POSTGRES_PASSWORD", "postgres"))
        .load()
    )
    return df


def load_odds_from_kafka(spark: SparkSession) -> DataFrame:
    """Load odds snapshots from Kafka."""
    df = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", settings.kafka_bootstrap_servers)
        .option("subscribe", KAFKA_RAW_ODDS)
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "false")
        .load()
    )
    parsed = df.select(F.from_json(F.col("value").cast("string"), ODDS_SCHEMA).alias("data"))
    return parsed.filter(F.col("data").isNotNull()).select("data.*")


def load_sentiment_from_kafka(spark: SparkSession) -> DataFrame:
    """Load processed sentiment from Kafka."""
    df = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", settings.kafka_bootstrap_servers)
        .option("subscribe", KAFKA_PROCESSED_SENTIMENT)
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "false")
        .load()
    )
    parsed = df.select(F.from_json(F.col("value").cast("string"), SENTIMENT_SCHEMA).alias("data"))
    return parsed.filter(F.col("data").isNotNull()).select("data.*")


def load_biometric_features_from_kafka(spark: SparkSession) -> DataFrame:
    """Load biometric features from Kafka."""
    df = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", settings.kafka_bootstrap_servers)
        .option("subscribe", KAFKA_PROCESSED_BIOMETRIC)
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "false")
        .load()
    )
    parsed = df.select(F.from_json(F.col("value").cast("string"), BIOMETRIC_SCHEMA).alias("data"))
    return parsed.filter(F.col("data").isNotNull()).select("data.*")


def compute_temporal_features_df(
    matches_df: DataFrame,
    events_df: DataFrame,
) -> DataFrame:
    """Compute temporal features from match events.

    Chains rolling averages, lag features, and rest days onto the match DataFrame.

    Args:
        matches_df: DataFrame of matches.
        events_df: DataFrame of match events.

    Returns:
        DataFrame with temporal features appended.
    """
    if events_df.isEmpty():
        return matches_df

    matches_with_goals = _join_goal_aggregates(matches_df, events_df)
    result = _add_rolling_features(matches_with_goals)
    result = _add_lag_and_rest_features(result)
    return result


def _join_goal_aggregates(matches_df: DataFrame, events_df: DataFrame) -> DataFrame:
    """Join goal aggregates onto matches DataFrame."""
    team_goals = (
        events_df.filter(F.col("event_type") == "goal")
        .groupBy("team_id", "match_id", "venue_type")
        .agg(
            F.count("*").alias("goals_scored"),
            F.sum(F.when(F.col("team_id") == F.col("home_team_id"), 1).otherwise(0)).alias(
                "home_goals"
            ),
            F.sum(F.when(F.col("team_id") == F.col("away_team_id"), 1).otherwise(0)).alias(
                "away_goals"
            ),
        )
    )

    return matches_df.join(
        team_goals,
        matches_df.match_id == team_goals.match_id,
        "left",
    )


def _add_rolling_features(df: DataFrame) -> DataFrame:
    """Add rolling average and standard deviation features."""
    window_5 = (
        Window.partitionBy("team_id")
        .orderBy("scheduled_at")
        .rowsBetween(
            ROLLING_WINDOW_5_START,
            ROLLING_WINDOW_5_END,
        )
    )
    window_10 = (
        Window.partitionBy("team_id")
        .orderBy("scheduled_at")
        .rowsBetween(
            ROLLING_WINDOW_10_START,
            ROLLING_WINDOW_10_END,
        )
    )

    return (
        df.withColumn(
            "rolling_avg_goals_5",
            F.avg("goals_scored").over(window_5),
        )
        .withColumn(
            "rolling_avg_goals_10",
            F.avg("goals_scored").over(window_10),
        )
        .withColumn(
            "rolling_std_goals_5",
            F.stddev("goals_scored").over(window_5),
        )
    )


def _add_lag_and_rest_features(df: DataFrame) -> DataFrame:
    """Add lag and rest day features."""
    team_order = Window.partitionBy("team_id").orderBy("scheduled_at")

    result = (
        df.withColumn(
            "lag_1_goals",
            F.lag("goals_scored", 1).over(team_order),
        )
        .withColumn(
            "lag_2_goals",
            F.lag("goals_scored", 2).over(team_order),
        )
        .withColumn(
            "lag_3_goals",
            F.lag("goals_scored", 3).over(team_order),
        )
    )

    result = result.withColumn(
        "rest_days",
        F.datediff("scheduled_at", F.lag("scheduled_at", 1).over(team_order)),
    ).fillna({"rest_days": 7})

    return result


def compute_odds_features(odds_df: DataFrame, matches_df: DataFrame) -> DataFrame:
    """Compute market/odds-derived features.

    Joins opening/closing odds onto matches and derives implied probabilities,
    line movement, cash-ticket divergence, and reverse line movement indicators.

    Args:
        odds_df: DataFrame of odds snapshots.
        matches_df: DataFrame of matches.

    Returns:
        DataFrame with odds-derived features appended.
    """
    if odds_df.isEmpty():
        return matches_df

    latest_odds = odds_df.groupBy("match_id").agg(
        F.first("home_odds").alias("opening_home_odds"),
        F.last("home_odds").alias("closing_home_odds"),
        F.first("away_odds").alias("opening_away_odds"),
        F.last("away_odds").alias("closing_away_odds"),
        F.first("captured_at").alias("opening_time"),
        F.last("captured_at").alias("closing_time"),
        F.first("cash_pct_home").alias("cash_pct_home"),
        F.first("ticket_pct_home").alias("ticket_pct_home"),
    )

    result = matches_df.join(latest_odds, "match_id", "left")

    result = (
        result.withColumn(
            "opening_implied_prob_home",
            F.when(F.col("opening_home_odds") > 0, 1.0 / F.col("opening_home_odds")).otherwise(0.0),
        )
        .withColumn(
            "closing_implied_prob_home",
            F.when(F.col("closing_home_odds") > 0, 1.0 / F.col("closing_home_odds")).otherwise(0.0),
        )
        .withColumn(
            "line_movement_spread",
            F.col("closing_home_odds") - F.col("opening_home_odds"),
        )
        .withColumn(
            "cash_ticket_divergence",
            F.col("cash_pct_home") - F.col("ticket_pct_home"),
        )
        .withColumn(
            "reverse_line_movement",
            F.when(
                (F.col("line_movement_spread") > 0)
                & (F.col("ticket_pct_home") < TICKET_PCT_HOME_THRESHOLD),
                1,
            )
            .when(
                (F.col("line_movement_spread") < 0)
                & (F.col("ticket_pct_home") > TICKET_PCT_HOME_THRESHOLD),
                1,
            )
            .otherwise(0),
        )
    )

    return result


def compute_biometric_features(
    matches_df: DataFrame,
    biometric_df: DataFrame,
) -> DataFrame:
    """Compute team biometric features."""
    if biometric_df.isEmpty():
        return matches_df

    latest_biometrics = biometric_df.groupBy("team_id").agg(
        F.avg("acwr").alias("team_avg_acwr"),
        F.avg("hrv").alias("team_avg_hrv"),
        F.avg("injury_risk").alias("team_injury_risk_score"),
    )

    result = (
        matches_df.join(
            latest_biometrics,
            matches_df.home_team_id == latest_biometrics.team_id,
            "left",
        )
        .withColumnRenamed("team_avg_acwr", "home_team_avg_acwr")
        .drop("team_id")
    )

    result = (
        result.join(
            latest_biometrics,
            result.away_team_id == latest_biometrics.team_id,
            "left",
        )
        .withColumnRenamed("team_avg_acwr", "away_team_avg_acwr")
        .drop("team_id")
    )

    return result


def compute_sentiment_features_df(
    matches_df: DataFrame,
    sentiment_df: DataFrame,
) -> DataFrame:
    """Compute sentiment features for teams."""
    if sentiment_df.isEmpty():
        return matches_df

    latest_sentiment = sentiment_df.groupBy("entity_id").agg(
        F.avg(F.when(F.col("source") == "twitter", F.col("score"))).alias("twitter_sentiment"),
        F.avg(F.when(F.col("source") == "reddit", F.col("score"))).alias("reddit_sentiment"),
        F.avg(F.when(F.col("source") == "news", F.col("score"))).alias("news_sentiment"),
        F.sum("volume").alias("sentiment_volume"),
    )

    result = (
        matches_df.join(
            latest_sentiment,
            matches_df.home_team_id == latest_sentiment.entity_id,
            "left",
        )
        .withColumnRenamed("twitter_sentiment", "home_twitter_sentiment")
        .drop("entity_id")
    )

    result = (
        result.join(
            latest_sentiment,
            result.away_team_id == latest_sentiment.entity_id,
            "left",
        )
        .withColumnRenamed("twitter_sentiment", "away_twitter_sentiment")
        .drop("entity_id")
    )

    return result


def add_context_features(df: DataFrame) -> DataFrame:
    """Add context features (is_home, day_of_week, etc.)."""
    result = df.withColumn("is_home", F.lit(1))

    result = result.withColumn(
        "day_of_week",
        F.dayofweek(F.col("scheduled_at")),
    )

    return result


def build_feature_vector(df: DataFrame) -> DataFrame:
    """Build final feature vector from all computed features."""
    feature_columns = [
        "match_id",
        "home_team_id",
        "away_team_id",
        "scheduled_at",
        "rolling_avg_goals_5",
        "rolling_avg_goals_10",
        "rolling_std_goals_5",
        "lag_1_goals",
        "lag_2_goals",
        "lag_3_goals",
        "rest_days",
        "opening_implied_prob_home",
        "closing_implied_prob_home",
        "line_movement_spread",
        "cash_ticket_divergence",
        "reverse_line_movement",
        "team_avg_acwr",
        "team_avg_hrv",
        "team_injury_risk_score",
        "twitter_sentiment",
        "reddit_sentiment",
        "news_sentiment",
        "sentiment_volume",
        "is_home",
        "day_of_week",
    ]

    existing_columns = [c for c in feature_columns if c in df.columns]
    return df.select(*existing_columns)


async def process_micro_batch(batch_df: DataFrame, batch_id: int) -> None:
    """Process a micro-batch of features."""
    logger.info("processing_batch", batch_id=batch_id, num_rows=batch_df.count())

    store_writer = FeatureStoreWriter()

    try:
        pandas_df = batch_df.toPandas()

        for _, row in pandas_df.iterrows():
            match_id = str(row["match_id"])
            features = {}

            for col in pandas_df.columns:
                if col not in ["match_id", "home_team_id", "away_team_id", "scheduled_at"]:
                    value = row.get(col)
                    if value is not None:
                        features[col] = (
                            float(value) if isinstance(value, (int, float)) else str(value)
                        )

            await store_writer.write_features(
                match_id=match_id,
                features=features,
            )

        logger.info("batch_processed", batch_id=batch_id, num_rows=len(pandas_df))
    except Exception as e:
        logger.error("batch_processing_error", batch_id=batch_id, error=str(e))
    finally:
        store_writer.close()


def run_batch_feature_computation(
    spark: SparkSession,
    start_date: str | None = None,
    end_date: str | None = None,
) -> None:
    """Run batch feature computation for historical matches."""
    logger.info("starting_batch_feature_computation", start_date=start_date, end_date=end_date)

    matches_df = load_matches_from_db(spark)

    if start_date:
        matches_df = matches_df.filter(F.col("scheduled_at") >= start_date)
    if end_date:
        matches_df = matches_df.filter(F.col("scheduled_at") <= end_date)

    matches_df = add_context_features(matches_df)

    feature_df = build_feature_vector(matches_df)

    store_writer = FeatureStoreWriter()

    try:
        pandas_df = feature_df.toPandas()

        for _, row in pandas_df.iterrows():
            match_id = str(row["match_id"])
            features = {}

            for col in pandas_df.columns:
                if col not in ["match_id", "home_team_id", "away_team_id", "scheduled_at"]:
                    value = row.get(col)
                    if value is not None and not pd.isna(value):
                        features[col] = (
                            float(value) if isinstance(value, (int, float)) else str(value)
                        )

            import asyncio

            asyncio.run(
                store_writer.write_features(
                    match_id=match_id,
                    features=features,
                )
            )

        logger.info("batch_feature_computation_complete", num_matches=len(pandas_df))
    except Exception as e:
        logger.error("batch_feature_computation_error", error=str(e))
    finally:
        store_writer.close()


def run_streaming_feature_pipeline(spark: SparkSession) -> None:
    """Run streaming feature pipeline."""
    logger.info("starting_streaming_feature_pipeline")

    matches_df = load_matches_from_db(spark)

    odds_df = load_odds_from_kafka(spark)
    sentiment_df = load_sentiment_from_kafka(spark)
    biometric_df = load_biometric_features_from_kafka(spark)

    base_features = add_context_features(matches_df)

    feature_df = compute_odds_features(odds_df, base_features)
    feature_df = compute_sentiment_features_df(sentiment_df, feature_df)
    feature_df = compute_biometric_features(biometric_df, feature_df)
    feature_df = build_feature_vector(feature_df)

    query = (
        feature_df.writeStream.foreachBatch(process_micro_batch)
        .option("checkpointLocation", "/tmp/spark_checkpoints/feature_engine")
        .trigger(processingTime="5 minutes")
        .start()
    )

    query.awaitTermination()


def main() -> None:
    """Main entry point for feature engineering pipeline."""
    import argparse
    import pandas as pd

    parser = argparse.ArgumentParser(description="Feature Engineering Pipeline")
    parser.add_argument("--mode", choices=["batch", "streaming"], default="batch")
    parser.add_argument(
        "--start-date", type=str, help="Start date for batch processing (YYYY-MM-DD)"
    )
    parser.add_argument("--end-date", type=str, help="End date for batch processing (YYYY-MM-DD)")

    args = parser.parse_args()

    spark = create_spark_session()

    try:
        if args.mode == "batch":
            run_batch_feature_computation(spark, args.start_date, args.end_date)
        else:
            run_streaming_feature_pipeline(spark)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
