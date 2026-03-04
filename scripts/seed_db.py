#!/usr/bin/env python3
"""Seed database with historical sports data.

This script loads historical match data into the database for model training
and testing purposes.

Usage:
    python scripts/seed_db.py --seasons 2021 2022 2023 2024 2025
    python scripts/seed_db.py --leagues premier_league --seasons 2024-25
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "libs"))

from sqlalchemy import select

from sports_common.db import DatabaseClient, db_client
from sports_common.logging import setup_logging, get_logger

setup_logging("seed-db")
logger = get_logger(__name__)


async def seed_teams(db: DatabaseClient, leagues: list[str]) -> dict[str, str]:
    """Seed teams and return mapping of external_id to internal UUID."""
    team_mapping = {}
    teams_data = [
        {
            "external_id": "epl-001",
            "provider": "api_sports",
            "name": "Manchester City",
            "short_name": "MCI",
            "league": "premier_league",
            "country": "England",
        },
        {
            "external_id": "epl-002",
            "provider": "api_sports",
            "name": "Arsenal",
            "short_name": "ARS",
            "league": "premier_league",
            "country": "England",
        },
        {
            "external_id": "epl-003",
            "provider": "api_sports",
            "name": "Liverpool",
            "short_name": "LIV",
            "league": "premier_league",
            "country": "England",
        },
        {
            "external_id": "epl-004",
            "provider": "api_sports",
            "name": "Chelsea",
            "short_name": "CHE",
            "league": "premier_league",
            "country": "England",
        },
        {
            "external_id": "epl-005",
            "provider": "api_sports",
            "name": "Manchester United",
            "short_name": "MUN",
            "league": "premier_league",
            "country": "England",
        },
    ]

    async with db.session() as session:
        from alembic.models import Team
        from uuid import uuid4

        for team_data in teams_data:
            if team_data["league"] not in leagues:
                continue
            team = Team(
                team_id=uuid4(),
                **team_data,
            )
            session.add(team)
            team_mapping[team_data["external_id"]] = str(team.team_id)

        await session.commit()
        logger.info("teams_seeded", count=len(team_mapping))

    return team_mapping


async def seed_matches(
    db: DatabaseClient,
    team_mapping: dict[str, str],
    leagues: list[str],
    seasons: list[str],
) -> dict[str, str]:
    """Seed matches and return mapping of external_id to internal UUID."""
    import random
    from uuid import uuid4
    from alembic.models import Match

    match_mapping = {}
    match_data = []

    for league in leagues:
        for season in seasons:
            for round_num in range(1, 39):
                teams = list(team_mapping.keys())
                if len(teams) < 2:
                    continue

                home_team = random.choice(teams)
                away_team = random.choice([t for t in teams if t != home_team])

                scheduled = datetime(
                    2024 + seasons.index(season),
                    random.randint(8, 12),
                    random.randint(1, 28),
                    random.randint(14, 20),
                    0,
                    0,
                    tzinfo=timezone.utc,
                )

                match_data.append(
                    {
                        "external_id": f"{league}-{season}-R{round_num}-{home_team}-{away_team}",
                        "provider": "api_sports",
                        "league": league,
                        "season": season,
                        "round": f"R{round_num}",
                        "home_team_id": team_mapping.get(home_team),
                        "away_team_id": team_mapping.get(away_team),
                        "scheduled_at": scheduled,
                        "venue": f"Stadium {round_num}",
                        "status": "finished",
                        "home_score": random.randint(0, 5),
                        "away_score": random.randint(0, 4),
                    }
                )

    async with db.session() as session:
        for m_data in match_data:
            match = Match(
                match_id=uuid4(),
                **m_data,
            )
            session.add(match)
            match_mapping[m_data["external_id"]] = str(match.match_id)

        await session.commit()
        logger.info("matches_seeded", count=len(match_mapping))

    return match_mapping


async def seed_odds(db: DatabaseClient, match_mapping: dict[str, str]) -> None:
    """Seed odds snapshots for matches."""
    import random
    from uuid import uuid4
    from alembic.models import OddsSnapshot
    from decimal import Decimal

    odds_data = []

    for match_ext_id, match_uuid in match_mapping.items():
        for sportsbook in ["draftkings", "fanduel", "betmgm"]:
            odds_data.append(
                {
                    "match_id": match_uuid,
                    "sportsbook": sportsbook,
                    "market_type": "moneyline",
                    "home_odds": Decimal(str(random.uniform(-150, 150))),
                    "away_odds": Decimal(str(random.uniform(-150, 150))),
                    "cash_pct_home": Decimal(str(random.uniform(0.3, 0.7))),
                    "ticket_pct_home": Decimal(str(random.uniform(0.3, 0.7))),
                    "captured_at": datetime.now(timezone.utc),
                }
            )

    async with db.session() as session:
        for o_data in odds_data:
            odds = OddsSnapshot(
                snapshot_id=uuid4(),
                **o_data,
            )
            session.add(odds)

        await session.commit()
        logger.info("odds_seeded", count=len(odds_data))


async def seed_biometrics(db: DatabaseClient) -> None:
    """Seed player biometric data."""
    import random
    from uuid import uuid4
    from alembic.models import PlayerBiometric
    from decimal import Decimal

    async with db.session() as session:
        from alembic.models import Player

        result = await session.execute(select(Player).limit(10))
        players = result.scalars().all()

        for player in players:
            for day_offset in range(30):
                recorded_at = datetime.now(timezone.utc)
                biometrics = [
                    ("hrv", random.uniform(30, 80), "ms"),
                    ("resting_hr", random.uniform(45, 70), "bpm"),
                    ("player_load", random.uniform(200, 800), "au"),
                ]

                for metric, value, unit in biometrics:
                    bio = PlayerBiometric(
                        biometric_id=uuid4(),
                        player_id=player.player_id,
                        source="catapult",
                        recorded_at=recorded_at,
                        metric_type=metric,
                        value=Decimal(str(value)),
                        unit=unit,
                    )
                    session.add(bio)

        await session.commit()
        logger.info("biometrics_seeded")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed database with historical data")
    parser.add_argument(
        "--leagues",
        nargs="+",
        default=["premier_league"],
        help="Leagues to seed",
    )
    parser.add_argument(
        "--seasons",
        nargs="+",
        default=["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"],
        help="Seasons to seed",
    )
    args = parser.parse_args()

    logger.info(
        "seeding_database",
        leagues=args.leagues,
        seasons=args.seasons,
    )

    await db_client.init_db()

    team_mapping = await seed_teams(db_client, args.leagues)
    match_mapping = await seed_matches(db_client, team_mapping, args.leagues, args.seasons)
    await seed_odds(db_client, match_mapping)
    await seed_biometrics(db_client)

    await db_client.close()
    logger.info("seeding_complete")


if __name__ == "__main__":
    asyncio.run(main())
