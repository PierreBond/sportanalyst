"""Try to backfill scores from football-data.co.uk CSV files."""
import io
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from pull_odds import canon

DB_URL = os.environ.get("DATABASE_URL_SYNC")

# football-data.co.uk CSV URLs for 2026-27 season
# Format: https://www.football-data.co.uk/mmz4281/2627/E0.csv (E0 = Premier League)
LEAGUE_CODES = {
    "premier_league": "E0",
    "championship": "E1",
    "serie_a": "I1",
    "serie_b": "I2",
    "la_liga": "SP1",
    "la_liga2": "SP2",
    "bundesliga1": "D1",
    "bundesliga2": "D2",
    "ligue_1": "F1",
    "ligue_2": "F2",
    "eredivisie": "N1",
    "primeira": "P1",
    "belgian_pro": "B1",
    "turkish_super": "T1",
    "eredivisie2": "N2",
}

BASE_URL = "https://www.football-data.co.uk/mmz4281/2627/"


def backfill_from_football_data(league: str, code: str, engine) -> int:
    """Download football-data.co.uk CSV and update match scores."""
    url = f"{BASE_URL}{code}.csv"
    
    try:
        df = pd.read_csv(url)
    except Exception as e:
        print(f"  [{league}] download failed: {e}")
        return 0
    
    if df.empty:
        print(f"  [{league}] empty CSV")
        return 0
    
    print(f"  [{league}] loaded {len(df)} rows, columns: {list(df.columns)[:5]}...")
    
    # football-data.co.uk columns: Div, Date, HomeTeam, AwayTeam, FTHG, FTAG, ...
    # We need to match by canonical team names
    updated = 0
    with engine.begin() as conn:
        for _, row in df.iterrows():
            home_team = canon(str(row.get("HomeTeam", "")))
            away_team = canon(str(row.get("AwayTeam", "")))
            fthg = row.get("FTHG")
            ftag = row.get("FTAG")
            
            if pd.isna(fthg) or pd.isna(ftag):
                continue
            
            cur = conn.execute(text("""
                SELECT m.match_id::text
                FROM matches m
                JOIN teams ht ON ht.team_id = m.home_team_id
                JOIN teams at ON at.team_id = m.away_team_id
                WHERE m.status = 'finished'
                  AND m.home_score IS NULL
                  AND canon(ht.name) = :home
                  AND canon(at.name) = :away
                LIMIT 1
            """), {"home": home_team, "away": away_team})
            # canon won't work in SQL - need Python-side matching
    
    return 0  # placeholder - need Python-side matching


if __name__ == "__main__":
    print("football-data.co.uk approach needs Python-side canonical matching")
    print("This is a placeholder - need to implement properly")
