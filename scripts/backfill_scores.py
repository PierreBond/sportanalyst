"""Backfill scores from football-data.co.uk CSV files for the 2026-27 season."""
import io
import os
import sys
import time
from pathlib import Path

import httpx
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from pull_odds import canon

DB_URL = os.environ.get("DATABASE_URL_SYNC")

# football-data.co.uk division codes for 2026-27 season
LEAGUE_CODES = {
    "premier_league": "E0",
    "serie_a": "I1",
    "la_liga": "SP1",
    "bundesliga": "D1",
    "ligue_1": "F1",
    "eredivisie": "N1",
    "brasileirao": None,  # not on football-data.co.uk
}

BASE_URL = "https://football-data.co.uk/mmz4281/2627/"


def backfill_league(league: str, code: str | None, engine) -> int:
    if code is None:
        print(f"  [{league}] not on football-data.co.uk, skipping")
        return 0

    url = f"{BASE_URL}{code}.csv"

    try:
        r = httpx.get(url, timeout=30)
    except Exception as e:
        print(f"  [{league}] download failed: {e}")
        return 0

    if r.status_code != 200:
        print(f"  [{league}] HTTP {r.status_code}")
        return 0

    try:
        df = pd.read_csv(io.BytesIO(r.content))
    except Exception as e:
        print(f"  [{league}] parse failed: {e}")
        return 0

    if df.empty:
        print(f"  [{league}] empty CSV")
        return 0

    # Canonicalize team names in the CSV data
    df["home_canon"] = df["HomeTeam"].apply(lambda x: canon(str(x)))
    df["away_canon"] = df["AwayTeam"].apply(lambda x: canon(str(x)))

    # Load finished matches lacking scores from DB
    with engine.connect() as conn:
        unfinished = conn.execute(text("""
            SELECT m.match_id::text, ht.name, at.name
            FROM matches m
            JOIN teams ht ON ht.team_id = m.home_team_id
            JOIN teams at ON at.team_id = m.away_team_id
            WHERE m.status = 'finished' AND m.home_score IS NULL
              AND m.league = :league
        """), {"league": league}).fetchall()

    # Build lookup: (home_canon, away_canon) -> [match_ids]
    match_lookup = {}
    for mid, home_name, away_name in unfinished:
        key = (canon(home_name), canon(away_name))
        match_lookup.setdefault(key, []).append(mid)

    updated = 0
    with engine.begin() as conn:
        for _, row in df.iterrows():
            fthg = row.get("FTHG")
            ftag = row.get("FTAG")
            if pd.isna(fthg) or pd.isna(ftag):
                continue

            key = (row["home_canon"], row["away_canon"])
            match_ids = match_lookup.get(key)
            if not match_ids:
                # Try reversed
                key = (row["away_canon"], row["home_canon"])
                match_ids = match_lookup.get(key)
                if not match_ids:
                    continue

            for mid in match_ids:
                conn.execute(text("""
                    UPDATE matches SET home_score = :h, away_score = :a
                    WHERE match_id = :mid AND home_score IS NULL
                """), {"h": int(fthg), "a": int(ftag), "mid": mid})
                updated += 1

    print(f"  [{league}] updated {updated} matches from {len(df)} CSV rows")
    return updated


def main():
    if not DB_URL:
        print("DATABASE_URL_SYNC not set")
        sys.exit(1)

    engine = create_engine(DB_URL)

    with engine.connect() as conn:
        cur = conn.execute(text("""
            SELECT count(*) FROM matches
            WHERE status = 'finished' AND home_score IS NULL
        """))
        missing = cur.fetchone()[0]
    print(f"Finished matches missing scores: {missing}")

    if missing == 0:
        print("Nothing to backfill.")
        return

    total_updated = 0
    for league, code in LEAGUE_CODES.items():
        print(f"Fetching {league} ({code})...")
        try:
            updated = backfill_league(league, code, engine)
            total_updated += updated
        except Exception as e:
            print(f"  [{league}] error: {e}")
        time.sleep(0.5)

    print(f"\nTotal updated: {total_updated}")

    with engine.connect() as conn:
        cur = conn.execute(text("""
            SELECT count(*) FROM matches
            WHERE status = 'finished' AND home_score IS NULL
        """))
        still_missing = cur.fetchone()[0]
    print(f"Still missing scores: {still_missing}")


if __name__ == "__main__":
    main()
