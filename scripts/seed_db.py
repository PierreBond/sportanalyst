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
sys.path.insert(0, str(Path(__file__).parent.parent / "alembic"))

from sqlalchemy import select

from sports_common.db import DatabaseClient, db_client
from sports_common.logging import setup_logging, get_logger

setup_logging("seed-db")
logger = get_logger(__name__)

TEAMS_BY_LEAGUE: dict[str, list[dict]] = {
    "premier_league": [
        {
            "external_id": "epl-001",
            "name": "Manchester City",
            "short_name": "MCI",
            "country": "England",
        },
        {"external_id": "epl-002", "name": "Arsenal", "short_name": "ARS", "country": "England"},
        {"external_id": "epl-003", "name": "Liverpool", "short_name": "LIV", "country": "England"},
        {"external_id": "epl-004", "name": "Chelsea", "short_name": "CHE", "country": "England"},
        {
            "external_id": "epl-005",
            "name": "Manchester United",
            "short_name": "MUN",
            "country": "England",
        },
        {"external_id": "epl-006", "name": "Tottenham", "short_name": "TOT", "country": "England"},
        {"external_id": "epl-007", "name": "Newcastle", "short_name": "NEW", "country": "England"},
        {
            "external_id": "epl-008",
            "name": "Manchester City",
            "short_name": "MCI",
            "country": "England",
        },
    ],
    "la_liga": [
        {"external_id": "ll-001", "name": "Real Madrid", "short_name": "RMA", "country": "Spain"},
        {"external_id": "ll-002", "name": "Barcelona", "short_name": "BAR", "country": "Spain"},
        {
            "external_id": "ll-003",
            "name": "Atletico Madrid",
            "short_name": "ATM",
            "country": "Spain",
        },
        {"external_id": "ll-004", "name": "Sevilla", "short_name": "SEV", "country": "Spain"},
        {"external_id": "ll-005", "name": "Real Sociedad", "short_name": "RSO", "country": "Spain"},
    ],
    "serie_a": [
        {"external_id": "sa-001", "name": "Inter Milan", "short_name": "INT", "country": "Italy"},
        {"external_id": "sa-002", "name": "AC Milan", "short_name": "MIL", "country": "Italy"},
        {"external_id": "sa-003", "name": "Juventus", "short_name": "JUV", "country": "Italy"},
        {"external_id": "sa-004", "name": "Napoli", "short_name": "NAP", "country": "Italy"},
        {"external_id": "sa-005", "name": "Roma", "short_name": "ROM", "country": "Italy"},
    ],
    "bundesliga": [
        {
            "external_id": "bl-001",
            "name": "Bayern Munich",
            "short_name": "BAY",
            "country": "Germany",
        },
        {
            "external_id": "bl-002",
            "name": "Borussia Dortmund",
            "short_name": "BVB",
            "country": "Germany",
        },
        {"external_id": "bl-003", "name": "RB Leipzig", "short_name": "RBL", "country": "Germany"},
        {"external_id": "bl-004", "name": "Leverkusen", "short_name": "LEV", "country": "Germany"},
        {
            "external_id": "bl-005",
            "name": "Eintracht Frankfurt",
            "short_name": "FRA",
            "country": "Germany",
        },
    ],
    "ligue_1": [
        {"external_id": "l1-001", "name": "PSG", "short_name": "PSG", "country": "France"},
        {"external_id": "l1-002", "name": "Marseille", "short_name": "MAR", "country": "France"},
        {"external_id": "l1-003", "name": "Lyon", "short_name": "LYO", "country": "France"},
        {"external_id": "l1-004", "name": "Monaco", "short_name": "MON", "country": "France"},
        {"external_id": "l1-005", "name": "Lille", "short_name": "LIL", "country": "France"},
    ],
}


async def seed_teams(db: DatabaseClient, leagues: list[str]) -> dict[str, str]:
    """Seed teams and return mapping of external_id to internal UUID."""
    team_mapping = {}
    teams_data = []

    for league in leagues:
        league_teams = TEAMS_BY_LEAGUE.get(league, [])
        for team in league_teams:
            teams_data.append(
                {
                    "external_id": team["external_id"],
                    "provider": "api_sports",
                    "name": team["name"],
                    "short_name": team["short_name"],
                    "league": league,
                    "country": team["country"],
                }
            )

    async with db.session() as session:
        from models import Team
        from uuid import uuid4

        for team_data in teams_data:
            if team_data["league"] not in leagues:
                continue

            existing = await session.execute(
                select(Team).where(
                    Team.external_id == team_data["external_id"],
                    Team.provider == team_data["provider"],
                )
            )
            existing_team = existing.scalar_one_or_none()
            if existing_team is not None:
                team_mapping[team_data["external_id"]] = str(existing_team.team_id)
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
    from models import Match

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
            existing = await session.execute(
                select(Match).where(Match.external_id == m_data["external_id"])
            )
            existing_match = existing.scalar_one_or_none()
            if existing_match is not None:
                match_mapping[m_data["external_id"]] = str(existing_match.match_id)
                continue

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
    from models import OddsSnapshot
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
    from models import PlayerBiometric
    from decimal import Decimal

    async with db.session() as session:
        from models import Player

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
        nargs="*",
        default=[],
        help="Leagues to seed (default: all from config/leagues.yaml)",
    )
    parser.add_argument(
        "--seasons",
        nargs="+",
        default=["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"],
        help="Seasons to seed",
    )
    args = parser.parse_args()

    if not args.leagues:
        try:
            from sports_common.league_config import get_league_config

            config = get_league_config()
            args.leagues = config.get_discovered_league_ids()
            if not args.leagues:
                args.leagues = ["premier_league"]
                logger.warning("no_configured_leagues_using_default", default=args.leagues)
        except Exception:
            args.leagues = ["premier_league"]
            logger.warning("config_load_failed_using_default", default=args.leagues)

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
