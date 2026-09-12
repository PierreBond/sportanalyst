"""Ingest full 2026 Brasileirão season from football-data.org."""
import json, os, re, sys
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
import httpx
from sqlalchemy import create_engine, text

BASE = Path(__file__).resolve().parent.parent

# Load env
env_path = BASE / ".env"
api_key = None
for line in env_path.read_text().splitlines():
    m = re.match(r'^FOOTBALL_DATA_ORG_KEY=(.+)$', line.strip())
    if m: api_key = m.group(1)
if not api_key: print("FOOTBALL_DATA_ORG_KEY not found"); sys.exit(1)

STATUS_MAP = {
    "FINISHED": "FT", "SCHEDULED": "scheduled", "TIMED": "scheduled",
    "POSTPONED": "postponed", "CANCELLED": "cancelled", "SUSPENDED": "suspended",
}

print("Fetching 2026 Brasileirão from football-data.org...")
r = httpx.get("https://api.football-data.org/v4/competitions/BSA/matches?season=2026",
              headers={"X-Auth-Token": api_key}, timeout=30)
matches = r.json().get("matches", [])
print(f"  {len(matches)} matches")

engine = create_engine(os.environ["DATABASE_URL_SYNC"])

# Parse into standard format
parsed = []
for f in matches:
    score = f.get("score", {})
    ht = f.get("homeTeam", {}) or {}
    at = f.get("awayTeam", {}) or {}
    venue = f.get("venue") or {}
    season_obj = f.get("season") or {}
    parsed.append({
        "external_id": f"footballdata_{f.get('id', '')}",
        "season": "2026",
        "league": "brasileirao",
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
        "provider": "football_data_org",
    })

# Upsert teams
teams = {}
for m in parsed:
    for ext, name in [(m["home_team_external_id"], m["home_team"]),
                      (m["away_team_external_id"], m["away_team"])]:
        if ext and name: teams[ext] = (name, "brasileirao")

team_count = 0
with engine.connect() as conn:
    for ext_id, (name, league_name) in teams.items():
        conn.execute(text("""
            INSERT INTO teams (team_id, external_id, provider, name, league)
            VALUES (:tid, :ext, 'football_data_org', :name, :league)
            ON CONFLICT (external_id, provider) DO UPDATE SET name = EXCLUDED.name
        """), {"tid": uuid4(), "ext": ext_id, "name": name, "league": league_name})
        team_count += 1
    conn.commit()
print(f"  {team_count} teams upserted")

# Upsert matches
saved = 0
skipped = 0
with engine.connect() as conn:
    for m in parsed:
        eid = m["external_id"]
        if not eid: skipped += 1; continue
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
            skipped += 1
    conn.commit()

status_counts = {}
for m in parsed: s = m["status"]; status_counts[s] = status_counts.get(s, 0) + 1
print(f"  {saved} matches upserted, {skipped} skipped")
print(f"  Statuses: {status_counts}")

with engine.connect() as conn:
    total = conn.execute(text("SELECT COUNT(*) FROM matches WHERE league='brasileirao' AND season='2026'")).scalar()
    ft = conn.execute(text("SELECT COUNT(*) FROM matches WHERE league='brasileirao' AND season='2026' AND status='FT'")).scalar()
    print(f"  Total Brasileirao 2026 in DB: {total} ({ft} FT)")
