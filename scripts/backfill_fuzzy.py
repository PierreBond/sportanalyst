"""Final automated backfill: fuzzy match openfootball JSON against unfinished matches."""
import json
import os
import sys
import traceback
from difflib import SequenceMatcher
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from pull_odds import canon

DB_URL = os.environ.get("DATABASE_URL_SYNC")

LEAGUE_URLS = {
    "premier_league": "en.1.json",
    "bundesliga": "de.1.json",
    "la_liga": "es.1.json",
    "serie_a": "it.1.json",
    "ligue_1": "fr.1.json",
    "eredivisie": "nl.1.json",
}

BASE = "https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/"


def canon_strong(n):
    import re, unicodedata
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode("ascii").lower().strip()
    n = n.replace("&", " and ")
    n = re.sub(r"[^a-z0-9\s]", " ", n)
    n = re.sub(r"\b\d+\b", " ", n)
    for w in ["fc", "sc", "cf", "ac", "afc", "ca", "rb", "ssc", "ss", "rc", "rcd", "sv",
              "vfl", "vfb", "tsg", "us", "club", "de", "del", "07", "munchen", "internazionale",
              "rennais", "munich", "inter", "rennes"]:
        n = re.sub(rf"\b{w}\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def fuzzy_match(name1, name2):
    c1 = canon_strong(name1)
    c2 = canon_strong(name2)
    return SequenceMatcher(None, c1, c2).ratio()


def backfill_league(league, code, engine):
    url = BASE + code
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
    except Exception:
        print("  [{}] parse failed".format(league))
        return 0
    print("  [{}] data type: {}".format(league, type(data).__name__))

    # Extract matches list
    matches = None
    if isinstance(data, dict):
        matches = data.get("matches")
    elif isinstance(data, list):
        matches = data
    else:
        print("  [{}] unexpected data type: {}".format(league, type(data).__name__))
        return 0

    if matches is None:
        print("  [{}] no 'matches' key in data".format(league))
        return 0

    print("  [{}] {} total matches in JSON".format(league, len(matches)))

    # Filter to scored matches
    scored = []
    for m in matches:
        if not isinstance(m, dict):
            continue
        score = m.get("score")
        if score and isinstance(score, dict) and score.get("ft"):
            ft = score["ft"]
            if isinstance(ft, list) and len(ft) == 2:
                scored.append(m)

    print("  [{}] {} scored matches in openfootball".format(league, len(scored)))

    # Load unfinished matches from DB
    with engine.connect() as conn:
        unfinished = conn.execute(text("""
            SELECT m.match_id::text, ht.name, at.name, m.scheduled_at
            FROM matches m
            JOIN teams ht ON ht.team_id = m.home_team_id
            JOIN teams at ON at.team_id = m.away_team_id
            WHERE m.status = 'finished' AND m.home_score IS NULL
              AND m.league = :league
        """), {"league": league}).fetchall()

    updated = 0
    with engine.begin() as conn:
        for mid, home_name, away_name, sched in unfinished:
            best = None
            best_score = 0.0
            for m in scored:
                try:
                    s = fuzzy_match(home_name, m["team1"]) + fuzzy_match(away_name, m["team2"])
                except Exception:
                    continue
                if s > best_score and s > 1.6:
                    best_score = s
                    best = m
            if best:
                ft = best["score"]["ft"]
                conn.execute(text("""
                    UPDATE matches SET home_score = :h, away_score = :a
                    WHERE match_id = :mid AND home_score IS NULL
                """), {"h": int(ft[0]), "a": int(ft[1]), "mid": mid})
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
    for league, code in LEAGUE_URLS.items():
        print("Fuzzy-matching {}...".format(league))
        try:
            updated = backfill_league(league, code, engine)
            total_updated += updated
        except Exception as e:
            print("  [{}] error: {}".format(league, e))
            traceback.print_exc()

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
