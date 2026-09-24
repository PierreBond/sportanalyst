"""Ingest 2026 season fixtures for all leagues from football-data.org.

Rate limit: free tier = 10 requests/minute. Script adds 7s delay between
leagues to stay safe. Total runtime ~2 minutes.
"""
import os, re, sys, time
from pathlib import Path
from datetime import datetime
from uuid import uuid4
import httpx
from sqlalchemy import create_engine, text

BASE = Path(__file__).resolve().parent.parent
env_path = BASE / ".env"

# Load env vars
api_key = None
db_url = None
for line in env_path.read_text().splitlines():
    line = line.strip()
    m = re.match(r'^FOOTBALL_DATA_ORG_KEY=(.+)$', line)
    if m: api_key = m.group(1)
    m = re.match(r'^DATABASE_URL_SYNC=(.+)$', line)
    if m: db_url = m.group(1)

if not api_key:
    print("FOOTBALL_DATA_ORG_KEY not found in .env"); sys.exit(1)
if not db_url:
    print("DATABASE_URL_SYNC not found in .env"); sys.exit(1)

LEAGUES = {
    "PL":    "premier_league",
    "PD":    "la_liga",
    "BL1":   "bundesliga",
    "SA":    "serie_a",
    "FL1":   "ligue_1",
    "DED":   "eredivisie",
    "J1":    "j1_league",
    "MLS":   "mls",
}

STATUS_MAP = {
    "FINISHED": "FT", "SCHEDULED": "scheduled", "TIMED": "scheduled",
    "IN_PLAY": "live", "PAUSED": "live", "AWARDED": "FT",
    "POSTPONED": "postponed", "CANCELLED": "cancelled", "SUSPENDED": "suspended",
}

SEASON = 2026

engine = create_engine(db_url)
total_upserted = 0

for i, (code, league_name) in enumerate(LEAGUES.items()):
    if i > 0:
        print(f"  Waiting 7s for rate limit...")
        time.sleep(7)

    print(f"\n[{code}] {league_name} {SEASON}...")
    url = f"https://api.football-data.org/v4/competitions/{code}/matches?season={SEASON}"
    r = httpx.get(url, headers={"X-Auth-Token": api_key}, timeout=30)

    if r.status_code == 429:
        print(f"  RATE LIMITED — skipping, will retry next run")
        continue
    if r.status_code != 200:
        print(f"  HTTP {r.status_code} — skipping")
        continue

    matches = r.json().get("matches", [])
    scheduled = [m for m in matches if m.get("status") in ("SCHEDULED", "TIMED")]
    print(f"  {len(matches)} total, {len(scheduled)} scheduled")

    if not matches:
        continue

    # Parse
    parsed = []
    for f in matches:
        score = f.get("score", {})
        ht = f.get("homeTeam") or {}
        at = f.get("awayTeam") or {}
        venue = f.get("venue") or {}
        parsed.append({
            "external_id": f"footballdata_{f.get('id', '')}",
            "season": str(SEASON),
            "league": league_name,
            "home_team": ht.get("name", ""),
            "away_team": at.get("name", ""),
            "home_team_external_id": f"footballdata_{ht.get('id', '')}",
            "away_team_external_id": f"footballdata_{at.get('id', '')}",
            "home_score": (score.get("fullTime") or {}).get("home"),
            "away_score": (score.get("fullTime") or {}).get("away"),
            "home_halftime_score": (score.get("halfTime") or {}).get("home"),
            "away_halftime_score": (score.get("halfTime") or {}).get("away"),
            "scheduled_at": f.get("utcDate", ""),
            "status": STATUS_MAP.get(f.get("status", ""), "scheduled"),
            "venue": venue.get("name", ""),
            "round": str(f.get("matchday", "")),
        })

    # Upsert teams
    teams = {}
    for m in parsed:
        for ext, name in [(m["home_team_external_id"], m["home_team"]),
                          (m["away_team_external_id"], m["away_team"])]:
            if ext and name: teams[ext] = name

    with engine.connect() as conn:
        for ext_id, name in teams.items():
            conn.execute(text("""
                INSERT INTO teams (team_id, external_id, provider, name, league)
                VALUES (:tid, :ext, 'football_data_org', :name, :league)
                ON CONFLICT (external_id, provider) DO UPDATE SET name = EXCLUDED.name
            """), {"tid": uuid4(), "ext": ext_id, "name": name, "league": league_name})
        conn.commit()

    # Upsert matches
    saved = 0
    with engine.connect() as conn:
        for m in parsed:
            eid = m["external_id"]
            if not eid: continue
            try:
                home_team_id = away_team_id = None
                if m["home_team_external_id"]:
                    row = conn.execute(text("SELECT team_id FROM teams WHERE external_id=:ext AND provider='football_data_org'"),
                                       {"ext": m["home_team_external_id"]}).fetchone()
                    if row: home_team_id = row[0]
                if m["away_team_external_id"]:
                    row = conn.execute(text("SELECT team_id FROM teams WHERE external_id=:ext AND provider='football_data_org'"),
                                       {"ext": m["away_team_external_id"]}).fetchone()
                    if row: away_team_id = row[0]

                sched = datetime.fromisoformat(m["scheduled_at"].replace("Z", "+00:00")) if m.get("scheduled_at") else None
                conn.execute(text("""
                    INSERT INTO matches (match_id, external_id, provider, league, season, round,
                        home_team_id, away_team_id, scheduled_at, venue, status,
                        home_score, away_score, home_halftime_score, away_halftime_score)
                    VALUES (:mid, :eid, 'football_data_org', :league, :season, :round,
                        :htid, :atid, :sched, :venue, :status,
                        :hs, :aws, :hhs, :ahs)
                    ON CONFLICT (external_id, provider) DO UPDATE SET
                        league = EXCLUDED.league,
                        season = EXCLUDED.season,
                        round = EXCLUDED.round,
                        home_team_id = EXCLUDED.home_team_id,
                        away_team_id = EXCLUDED.away_team_id,
                        scheduled_at = EXCLUDED.scheduled_at,
                        venue = EXCLUDED.venue,
                        status = EXCLUDED.status,
                        home_score = COALESCE(EXCLUDED.home_score, matches.home_score),
                        away_score = COALESCE(EXCLUDED.away_score, matches.away_score),
                        home_halftime_score = COALESCE(EXCLUDED.home_halftime_score, matches.home_halftime_score),
                        away_halftime_score = COALESCE(EXCLUDED.away_halftime_score, matches.away_halftime_score),
                        updated_at = NOW()
                    WHERE matches.status IN ('scheduled', 'postponed') OR matches.season != :season
                """), {
                    "mid": uuid4(), "eid": eid,
                    "league": m["league"], "season": m["season"], "round": m["round"],
                    "htid": home_team_id, "atid": away_team_id,
                    "sched": sched, "venue": m["venue"], "status": m["status"],
                    "hs": m["home_score"], "aws": m["away_score"],
                    "hhs": m["home_halftime_score"], "ahs": m["away_halftime_score"],
                })
                saved += 1
            except Exception as e:
                print(f"  FAIL {eid}: {e}")
        conn.commit()

    total_upserted += saved
    print(f"  {saved} matches upserted")

print(f"\n{'='*50}")
print(f"Total: {total_upserted} matches upserted across {len(LEAGUES)} leagues")

# Summary
with engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT league, COUNT(*) as total,
               COUNT(*) FILTER (WHERE status='scheduled') as upcoming
        FROM matches WHERE season='2026'
        GROUP BY league ORDER BY upcoming DESC
    """)).fetchall()
    print(f"\nLeague summary (2026 season):")
    for league, total, upcoming in rows:
        print(f"  {league:<20} {total:>4} matches, {upcoming:>4} upcoming")
