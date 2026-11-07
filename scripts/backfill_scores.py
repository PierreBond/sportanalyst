"""Backfill scores for 'finished' matches from openfootball/football.json (GitHub, no API key).

Downloads the 2026-27 season JSON for each covered league, canonicalizes team names,
and updates matches that have status='finished' but no score.
"""
import io
import json
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

LEAGUE_URLS = {
    "premier_league": "https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/en.1.json",
    "bundesliga": "https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/de.1.json",
    "la_liga": "https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/es.1.json",
    "serie_a": "https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/it.1.json",
    "ligue_1": "https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/fr.1.json",
    "eredivisie": "https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/nl.1.json",
}

UNSUPPORTED = ["brasileirao"]


def backfill_league(league, url, engine):
    try:
        r = httpx.get(url, timeout=30)
    except Exception as e:
        print("  [{}] request failed: {}".format(league, e))
        return 0

    if r.status_code != 200:
        print("  [{}] HTTP {}".format(league, r.status_code))
        return 0

    try:
        data = json.loads(r.text)
    except Exception as e:
        print("  [{}] parse failed: {}".format(league, e))
        return 0

    matches = data.get("matches", [])
    if not matches:
        print("  [{}] no matches found".format(league))
        return 0

    score_map = {}
    for m in matches:
        score = m.get("score")
        if not score or "ft" not in score:
            continue
        ft = score["ft"]
        if len(ft) != 2 or ft[0] is None or ft[1] is None:
            continue
        key = (canon(m["team1"]), canon(m["team2"]), m["date"])
        score_map[key] = (int(ft[0]), int(ft[1]))

    n_scores = len(score_map)
    print("  [{}] {} matches in CSV, {} with scores".format(league, len(matches), n_scores))

    with engine.connect() as conn:
        unfinished = conn.execute(text("""
            SELECT m.match_id::text, ht.name, at.name, m.scheduled_at
            FROM matches m
            JOIN teams ht ON ht.team_id = m.home_team_id
            JOIN teams at ON at.team_id = m.away_team_id
            WHERE m.status = 'finished' AND m.home_score IS NULL
              AND m.league = :league
        """), {"league": league}).fetchall()

    match_lookup = {}
    for mid, home_name, away_name, sched in unfinished:
        key = (canon(home_name), canon(away_name), str(sched.date()))
        match_lookup.setdefault(key, []).append(mid)

    updated = 0
    with engine.begin() as conn:
        for key, score in score_map.items():
            match_ids = match_lookup.get(key)
            if not match_ids:
                continue
            h, a = score
            for mid in match_ids:
                conn.execute(text("""
                    UPDATE matches SET home_score = :h, away_score = :a
                    WHERE match_id = :mid AND home_score IS NULL
                """), {"h": h, "a": a, "mid": mid})
                updated += 1

    print("  [{}] updated {} matches".format(league, updated))
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
    print("Finished matches missing scores: {}".format(missing))

    if missing == 0:
        print("Nothing to backfill.")
        return

    total_updated = 0
    for league, url in LEAGUE_URLS.items():
        print("Fetching {}...".format(league))
        try:
            updated = backfill_league(league, url, engine)
            total_updated += updated
        except Exception as e:
            print("  [{}] error: {}".format(league, e))
        time.sleep(0.5)

    print("\nTotal updated: {}".format(total_updated))

    with engine.connect() as conn:
        cur = conn.execute(text("""
            SELECT count(*) FROM matches
            WHERE status = 'finished' AND home_score IS NULL
        """))
        still_missing = cur.fetchone()[0]
    print("Still missing scores: {}".format(still_missing))


if __name__ == "__main__":
    main()
