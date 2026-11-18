"""Ingest free historical results from football-data.co.uk into the database.

The CSV files need no account, no key and no card: one file per league per
season, with every result. The model only had three seasons of its own data,
which leaves clubs that were promoted or had a bad run with almost no
history -- and a club with no history gets the default Elo, which is what
produces the absurd edges on the value-bets board.

Usage:
    python scripts/ingest_history.py --dry-run   # report, write nothing
    python scripts/ingest_history.py             # ingest (idempotent)

Re-running is safe: matches are keyed on (external_id, provider) and any
match that already exists in the database (same league, date and clubs) is
skipped, so overlapping seasons are never double counted.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
from difflib import get_close_matches
from pathlib import Path
from uuid import uuid4

import httpx
import pandas as pd
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libs"))
from sports_common.team_map import canon_team  # noqa: E402

BASE = "https://football-data.co.uk/mmz4281/{code}/{div}.csv"
PROVIDER = "football_data_co_uk"

LEAGUES = {
    "premier_league": "E0",
    "la_liga": "SP1",
    "serie_a": "I1",
    "bundesliga": "D1",
    "ligue_1": "F1",
    "eredivisie": "N1",
}
FIRST_SEASON = 2005  # season starting year; 2005 -> the 2005/06 season
LAST_SEASON = 2021   # season starting year; 2021 -> the 2021/22 season

# football-data.co.uk short names -> the canonical club class used by the
# model. Only needed where the short name does not canonicalize to a club we
# already have.
ALIASES = {
    "man city": "manchester city",
    "man united": "manchester",
    "man utd": "manchester",
    "nottm forest": "nottingham forest",
    "nott m forest": "nottingham forest",
    "tottenham": "tottenham",
    "spurs": "tottenham",
    "wolves": "wolves",
    "wolverhampton": "wolves",
    "ath madrid": "atletico madrid",
    "ath bilbao": "athletic",
    "barca": "barcelona",
    "sociedad": "real sociedad",
    "betis": "real betis",
    "celta": "celta vigo",
    "espanol": "espanyol",
    "deportivo": "deportivo la",
    "la coruna": "deportivo la",
    "racing santander": "real racing santander",
    "santander": "real racing santander",
    "vallecano": "rayo vallecano",
    "ruth": "real racing santander",
    "racing sant": "real racing santander",
    "milan": "milan",
    "inter": "inter",
    "roma": "as roma",
    "lazio": "lazio",
    "verona": "hellas verona",
    "napoli": "napoli",
    "dortmund": "borussia dortmund",
    "m'gladbach": "borussia monchengladbach",
    "m gladbach": "borussia monchengladbach",
    "gladbach": "borussia monchengladbach",
    "leverkusen": "bayer leverkusen",
    "ein frankfurt": "eintracht frankfurt",
    "mainz": "fsv mainz",
    "hamburg": "hamburger",
    "hertha": "hertha berlin",
    "kiel": "holstein kiel",
    "paris sg": "paris saint germain",
    "psg": "paris saint germain",
    "brest": "stade brestois",
    "st etienne": "saint etienne",
    "clermont": "clermont foot",
    "troyes": "estac troyes",
    "rennes": "rennes",
    "hull": "hull city",
    "sheffield united": "sheffield utd",
    "coventry": "coventry city",
    "den haag": "ado den haag",
    "rkc waalwijk": "waalwijk",
    "de graafschap": "graafschap",
    "twente": "twente",
    "heerenveen": "heerenveen",
    "sparta": "sparta",
    "az alkmaar": "az alkmaar",
    "hv": "excelsior",
    "excelsior": "excelsior",
    "pec zwolle": "pec zwolle",
    "nac breda": "nac breda",
    "fortuna sittard": "fortuna sittard",
    "go ahead eagles": "go ahead eagles",
    "den bosch": "den bosch",
    "mvv": "mvv",
    "vvv venlo": "vvv venlo",
    "vitesse": "vitesse",
    "nec": "nec nijmegen",
    "nijmegen": "nec nijmegen",
    "cambuur": "cambuur",
    "ajaccio gfco": "ajaccio",
    "for sittard": "fortuna sittard",
    "roda jc": "roda",
    "zwolle": "pec zwolle",
    "hercules": "heracles",
    "st etienne ": "saint etienne",
}


def season_codes() -> list[tuple[int, str]]:
    return [
        (year, f"{year % 100:02d}{(year + 1) % 100:02d}")
        for year in range(FIRST_SEASON, LAST_SEASON + 1)
    ]


def fetch_season(client: httpx.Client, code: str, div: str) -> pd.DataFrame | None:
    """Download and parse one league season file."""
    try:
        response = client.get(BASE.format(code=code, div=div))
    except Exception:
        return None
    if response.status_code != 200:
        return None
    lines = response.text.lstrip("\ufeff").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("Div,")), None)
    if start is None:
        return None
    try:
        df = pd.read_csv(io.StringIO("\n".join(lines[start:])), encoding="latin-1")
    except Exception:
        return None
    if "FTHG" not in df.columns:
        return None
    df = df.dropna(subset=["FTHG", "FTAG", "HomeTeam", "AwayTeam", "Date"])
    if df.empty:
        return None
    return df


def build_rows(frames: list[tuple[str, int, str, pd.DataFrame]]) -> pd.DataFrame:
    rows = []
    for league, season, code, df in frames:
        dates = pd.to_datetime(df["Date"], dayfirst=True, format="mixed", errors="coerce")
        for i, (date, home, away, hg, ag) in enumerate(
            zip(dates, df["HomeTeam"], df["AwayTeam"], df["FTHG"], df["FTAG"])
        ):
            if pd.isna(date):
                continue
            rows.append({
                "external_id": f"fd_{league}_{code}_{i:04d}",
                "league": league,
                "season": str(season),
                "scheduled_at": date.to_pydatetime(),
                "home_name": str(home).strip(),
                "away_name": str(away).strip(),
                "home_score": int(hg),
                "away_score": int(ag),
            })
    return pd.DataFrame(rows)


def resolve_club(
    fd_name: str,
    db_classes: dict[str, str],
    db_class_set: set[str],
) -> tuple[str, str]:
    """Return (canonical class, display name) for a football-data club name."""
    alias = ALIASES.get(fd_name.strip().lower())
    if alias:
        return alias, db_classes.get(alias, alias)
    class_name = canon_team(fd_name)
    if class_name in db_class_set:
        return class_name, db_classes[class_name]
    return class_name, fd_name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="report only")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL_SYNC")
    if not db_url:
        raise SystemExit("DATABASE_URL_SYNC is not set")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        db_teams = conn.execute(text("""
            SELECT t.name, t.league, count(m.match_id) AS n
            FROM teams t LEFT JOIN matches m
              ON m.home_team_id = t.team_id OR m.away_team_id = t.team_id
            GROUP BY t.name, t.league
        """)).fetchall()
        db_matches = conn.execute(text("""
            SELECT m.league, m.scheduled_at::date AS d,
                   ht.name AS home, at.name AS away
            FROM matches m
            JOIN teams ht ON ht.team_id = m.home_team_id
            JOIN teams at ON at.team_id = m.away_team_id
        """)).fetchall()

    # canonical class -> the most used database name for that class
    class_counts: dict[str, dict[str, int]] = {}
    for name, _league, n in db_teams:
        cls = canon_team(name)
        class_counts.setdefault(cls, {})[name] = int(n or 0)
    db_classes = {
        cls: max(names.items(), key=lambda kv: kv[1])[0]
        for cls, names in class_counts.items()
    }
    db_class_set = set(db_classes)

    # (league, date, home class, away class) keys already in the database
    existing: set[tuple] = set()
    for league, day, home, away in db_matches:
        existing.add((league, day, canon_team(home), canon_team(away)))

    print(f"database: {len(db_teams)} team rows, {len(db_class_set)} canonical classes, "
          f"{len(db_matches)} matches")

    frames: list[tuple[str, int, str, pd.DataFrame]] = []
    with httpx.Client(timeout=60, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0"}) as client:
        for league, div in LEAGUES.items():
            for season, code in season_codes():
                df = fetch_season(client, code, div)
                if df is None:
                    print(f"  {league} {code}: unavailable")
                    continue
                frames.append((league, season, code, df))
                print(f"  {league} {code}: {len(df)} matches")

    rows = build_rows(frames)
    print(f"\nfootball-data rows: {len(rows):,}")

    resolved: list[tuple[str, str]] = []
    for name in sorted(set(rows["home_name"]) | set(rows["away_name"])):
        resolved.append((name, resolve_club(name, db_classes, db_class_set)[0]))

    new_classes = {cls for name, cls in resolved if cls not in db_class_set}
    matched = {cls for name, cls in resolved if cls in db_class_set}
    print(f"distinct football-data clubs: {len(resolved)}")
    print(f"  resolve to a club we already have: {len(matched)}")
    print(f"  new clubs (need a team row):      {len(new_classes)}")

    print("\nclubs that need an alias (closest existing class):")
    needs_alias = 0
    for name, cls in resolved:
        if cls in db_class_set:
            continue
        candidates = get_close_matches(cls, sorted(db_class_set), n=2, cutoff=0.72)
        substring = [c for c in db_class_set if cls in c or c in cls]
        if candidates or substring:
            needs_alias += 1
            print(f"  {name:26s} -> {cls:26s} candidates={candidates + substring[:2]}")
    print(f"  ({needs_alias} to review, the rest are genuinely new clubs)")

    print("\nnew clubs (a review list, not an error):")
    for name, cls in resolved:
        if cls not in db_class_set:
            print(f"  {name:26s} -> {cls}")

    rows["home_class"] = rows["home_name"].map(dict(resolved))
    rows["away_class"] = rows["away_name"].map(dict(resolved))
    # which league a club belongs to, taken from the files it appears in
    class_league: dict[str, str] = {}
    for name, cls in resolved:
        leagues = {lg for lg, _season, _code, df in frames
                   if name in set(df["HomeTeam"]) | set(df["AwayTeam"])}
        class_league.setdefault(cls, sorted(leagues)[0] if leagues else "unknown")
    rows["key"] = [
        (league, day.date() if hasattr(day, "date") else day, home, away)
        for league, day, home, away in zip(
            rows["league"], rows["scheduled_at"], rows["home_class"], rows["away_class"])
    ]
    duplicates = rows["key"].isin(existing)
    print(f"\nrows already in the database (same league, date, clubs): {int(duplicates.sum()):,}")
    fresh = rows[~duplicates].copy()
    print(f"rows to insert: {len(fresh):,}")
    print(f"  seasons: {sorted(fresh['season'].unique())}")

    if args.dry_run:
        print("\ndry run: nothing written")
        return

    # team rows for clubs we do not have yet
    with engine.begin() as conn:
        existing_classes = {
            canon_team(row[0]) for row in conn.execute(text("SELECT name FROM teams")).all()
        }
        for cls in sorted(new_classes):
            if cls in existing_classes:
                continue
            sample = next(name for name, c in resolved if c == cls)
            slug = re.sub(r"[^a-z0-9]+", "_", sample.lower()).strip("_")
            conn.execute(text("""
                INSERT INTO teams (team_id, external_id, provider, name, league)
                VALUES (:tid, :ext, :provider, :name, :league)
                ON CONFLICT (external_id, provider) DO NOTHING
            """), {
                "tid": uuid4(),
                "ext": f"fd_{slug}",
                "provider": PROVIDER,
                "name": sample,
                "league": class_league.get(cls, "unknown"),
            })
        print(f"inserted team rows for {len(new_classes)} new clubs")

    # map canonical class -> the team id to attach the matches to. An existing
    # database row wins over the history rows, so a club keeps one row.
    with engine.connect() as conn:
        rows_teams = conn.execute(text("""
            SELECT team_id::text, name, provider FROM teams
        """)).fetchall()
    team_id_by_class: dict[str, str] = {}
    for team_id, name, provider in rows_teams:
        cls = canon_team(name)
        if cls not in team_id_by_class or provider != PROVIDER:
            team_id_by_class[cls] = team_id

    inserted = 0
    with engine.begin() as conn:
        for row in fresh.itertuples():
            home_id = team_id_by_class.get(row.home_class)
            away_id = team_id_by_class.get(row.away_class)
            if not home_id or not away_id:
                continue
            conn.execute(text("""
                INSERT INTO matches (match_id, external_id, provider, league, season,
                                     home_team_id, away_team_id, scheduled_at,
                                     status, home_score, away_score)
                VALUES (:mid, :ext, :provider, :league, :season, :hid, :aid, :at,
                        'FT', :hs, :as_)
                ON CONFLICT (external_id, provider) DO NOTHING
            """), {
                "mid": uuid4(),
                "ext": row.external_id,
                "provider": PROVIDER,
                "league": row.league,
                "season": row.season,
                "hid": home_id,
                "aid": away_id,
                "at": row.scheduled_at,
                "hs": row.home_score,
                "as_": row.away_score,
            })
            inserted += 1
    print(f"inserted {inserted:,} matches")


if __name__ == "__main__":
    main()
