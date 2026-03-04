#!/usr/bin/env python3
"""Backfill feature_store table for historical matches.

This script computes features for all historical matches in the database
and populates the feature_store table.

Usage:
    python scripts/backfill_features.py --seasons 2021-22 2022-23 2023-24 2024-25
    python scripts/backfill_features.py --all-seasons
    python scripts/backfill_features.py --start-date 2024-01-01 --end-date 2025-05-31
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
import pandas as pd
from sqlalchemy import select, text

sys.path.insert(0, str(Path(__file__).parent.parent))

from alembic.models import Match, Team, OddsSnapshot, MatchEvent, SentimentScore, PlayerBiometric
from sports_common.config import settings
from sports_common.db import get_async_session
from sports_common.logging import setup_logging
from services.feature_engine.src.store import FeatureStoreWriter

logger = structlog.get_logger(__name__)

FEATURE_VERSION = "v1.0"


async def get_matches_to_backfill(
    seasons: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Get matches that need features computed."""
    async with get_async_session() as session:
        query = select(Match).where(Match.status == "finished")

        if seasons:
            query = query.where(Match.season.in_(seasons))

        if start_date:
            start_dt = datetime.fromisoformat(start_date)
            query = query.where(Match.scheduled_at >= start_dt)

        if end_date:
            end_dt = datetime.fromisoformat(end_date)
            query = query.where(Match.scheduled_at <= end_dt)

        result = await session.execute(query)
        matches = result.scalars().all()

        return [
            {
                "match_id": str(m.match_id),
                "home_team_id": str(m.home_team_id) if m.home_team_id else None,
                "away_team_id": str(m.away_team_id) if m.away_team_id else None,
                "scheduled_at": m.scheduled_at,
                "league": m.league,
                "season": m.season,
            }
            for m in matches
        ]


async def get_team_performance_features(match_id: str, as_of: datetime) -> dict[str, float]:
    """Compute team performance features from historical match events."""
    async with get_async_session() as session:
        stmt = text("""
            SELECT 
                me.team_id,
                COUNT(*) as matches_played,
                SUM(CASE WHEN me.event_type = 'goal' THEN 1 ELSE 0 END) as goals_scored,
                AVG(CASE WHEN me.event_type = 'shot_on_target' THEN 1 ELSE 0 END) as shot_accuracy
            FROM match_events me
            JOIN matches m ON me.match_id = m.match_id
            WHERE m.scheduled_at < :as_of
            GROUP BY me.team_id
        """)
        result = await session.execute(stmt, {"as_of": as_of})
        rows = result.fetchall()

        features = {}
        for row in rows:
            team_id = str(row.team_id)
            features[f"team_{team_id}_matches"] = float(row.matches_played)
            features[f"team_{team_id}_goals"] = float(row.goals_scored)
            features[f"team_{team_id}_shot_accuracy"] = float(row.shot_accuracy or 0)

        return features


async def get_odds_features(match_id: str) -> dict[str, float]:
    """Get odds-derived features for a match."""
    async with get_async_session() as session:
        stmt = select(OddsSnapshot).where(
            OddsSnapshot.match_id == match_id
        ).order_by(OddsSnapshot.captured_at)

        result = await session.execute(stmt)
        snapshots = result.scalars().all()

        if not snapshots:
            return {}

        first = snapshots[0]
        last = snapshots[-1]

        features = {}

        if first.home_odds and first.home_odds > 0:
            features["opening_implied_prob_home"] = 1.0 / first.home_odds

        if last.home_odds and last.home_odds > 0:
            features["closing_implied_prob_home"] = 1.0 / last.home_odds

        if first.home_odds and last.home_odds:
            features["line_movement_spread"] = float(last.home_odds - first.home_odds)

        if last.cash_pct_home is not None and last.ticket_pct_home is not None:
            features["cash_ticket_divergence"] = float(last.cash_pct_home - last.ticket_pct_home)

            rlm = (
                (features.get("line_movement_spread", 0) > 0 and last.ticket_pct_home < 0.5) or
                (features.get("line_movement_spread", 0) < 0 and last.ticket_pct_home > 0.5)
            )
            features["reverse_line_movement"] = 1.0 if rlm else 0.0

        return features


async def get_sentiment_features(home_team_id: str, away_team_id: str, as_of: datetime) -> dict[str, float]:
    """Get sentiment features for teams."""
    async with get_async_session() as session:
        cutoff = as_of - pd.Timedelta(hours=24)

        stmt = text("""
            SELECT 
                entity_id,
                source,
                AVG(score) as avg_score,
                SUM(volume) as total_volume
            FROM sentiment_scores
            WHERE captured_at >= :cutoff
            AND entity_id IN (:home_team_id, :away_team_id)
            GROUP BY entity_id, source
        """)

        result = await session.execute(stmt, {
            "cutoff": cutoff,
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
        })
        rows = result.fetchall()

        features = {}
        for row in rows:
            entity = "home" if str(row.entity_id) == home_team_id else "away"
            source = row.source

            features[f"team_sentiment_{source}_{entity}"] = float(row.avg_score or 0)
            features[f"sentiment_volume_{entity}"] = float(row.total_volume or 0)

        return features


async def get_biometric_features(team_id: str, as_of: datetime) -> dict[str, float]:
    """Get biometric features for a team."""
    async with get_async_session() as session:
        cutoff = as_of - pd.Timedelta(days=7)

        stmt = text("""
            SELECT 
                pb.player_id,
                AVG(pb.value) as avg_value
            FROM player_biometrics pb
            JOIN players p ON pb.player_id = p.player_id
            WHERE p.team_id = :team_id
            AND pb.recorded_at >= :cutoff
            AND pb.metric_type IN ('hrv', 'player_load')
            GROUP BY pb.player_id
        """)

        result = await session.execute(stmt, {
            "team_id": team_id,
            "cutoff": cutoff,
        })
        rows = result.fetchall()

        if not rows:
            return {}

        avg_hrv = sum(r.avg_value for r in rows) / len(rows)
        return {
            "team_avg_hrv": float(avg_hrv),
            "team_avg_acwr": 1.0,
        }


async def compute_all_features_for_match(match: dict[str, Any]) -> dict[str, Any]:
    """Compute all features for a single match."""
    match_id = match["match_id"]
    as_of = match["scheduled_at"]

    features = {}

    perf_features = await get_team_performance_features(match_id, as_of)
    features.update(perf_features)

    odds_features = await get_odds_features(match_id)
    features.update(odds_features)

    if match["home_team_id"] and match["away_team_id"]:
        sent_features = await get_sentiment_features(
            match["home_team_id"],
            match["away_team_id"],
            as_of,
        )
        features.update(sent_features)

        home_bio = await get_biometric_features(match["home_team_id"], as_of)
        away_bio = await get_biometric_features(match["away_team_id"], as_of)

        for key, value in home_bio.items():
            features[f"home_{key}"] = value
        for key, value in away_bio.items():
            features[f"away_{key}"] = value

    features["is_home"] = 1.0
    features["day_of_week"] = float(as_of.weekday())

    if as_of.astimezone(timezone.utc).tzinfo is not None:
        rest_days = 7
    else:
        rest_days = 7
    features["rest_days"] = float(rest_days)

    return features


async def backfill_features(
    seasons: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    batch_size: int = 100,
) -> int:
    """Backfill features for all historical matches.

    Returns:
        Number of matches processed
    """
    logger.info("starting_backfill", seasons=seasons, start_date=start_date, end_date=end_date)

    matches = await get_matches_to_backfill(seasons, start_date, end_date)
    logger.info("matches_found", count=len(matches))

    if not matches:
        logger.warning("no_matches_found")
        return 0

    store_writer = FeatureStoreWriter()
    processed = 0

    try:
        for i in range(0, len(matches), batch_size):
            batch = matches[i:i + batch_size]

            features_list = []
            for match in batch:
                features = await compute_all_features_for_match(match)
                features_list.append({
                    "match_id": match["match_id"],
                    "features": features,
                })

            await store_writer.write_features_batch(features_list)
            processed += len(batch)

            logger.info("batch_processed", processed=processed, total=len(matches))

    finally:
        store_writer.close()

    logger.info("backfill_complete", processed=processed)
    return processed


async def main() -> None:
    """Main entry point."""
    setup_logging()

    parser = argparse.ArgumentParser(description="Backfill feature store")
    parser.add_argument(
        "--seasons",
        nargs="+",
        help="Seasons to backfill (e.g., 2021-22 2022-23)",
    )
    parser.add_argument(
        "--all-seasons",
        action="store_true",
        help="Backfill all seasons",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for processing",
    )

    args = parser.parse_args()

    seasons = args.seasons if args.seasons else None

    if args.all_seasons:
        seasons = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]

    if not seasons and not args.start_date and not args.end_date:
        parser.error("Specify --seasons, --all-seasons, or --start-date/--end-date")

    await backfill_features(
        seasons=seasons,
        start_date=args.start_date,
        end_date=args.end_date,
        batch_size=args.batch_size,
    )


if __name__ == "__main__":
    asyncio.run(main())
